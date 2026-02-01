#!/bin/bash
################################################################################
# Remote Access System - Automated Deployment Script
# 
# This script automates the deployment of the Remote Access Server on Ubuntu/Debian
# Run with sudo: sudo bash deploy.sh
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/remote-access"
SERVICE_NAME="remote-access"
WEB_DIR="/var/www/remote-access"
DOMAIN=""

# Functions
print_header() {
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}================================${NC}"
}

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then 
        print_error "Please run as root (use sudo)"
        exit 1
    fi
}

install_dependencies() {
    print_header "Installing System Dependencies"
    
    apt update
    apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        sqlite3 \
        libsqlite3-dev \
        build-essential \
        nginx \
        certbot \
        python3-certbot-nginx \
        ufw
    
    print_info "Dependencies installed successfully"
}

setup_firewall() {
    print_header "Configuring Firewall"
    
    # Enable UFW if not already enabled
    ufw --force enable
    
    # Allow SSH (important!)
    ufw allow ssh
    
    # Allow HTTP/HTTPS
    ufw allow 80/tcp
    ufw allow 443/tcp
    
    # Allow UDP port range for sessions
    ufw allow 50000:60000/udp
    
    # Reload firewall
    ufw reload
    
    print_info "Firewall configured successfully"
    ufw status
}

create_system_user() {
    print_header "Creating System User"
    
    if ! id -u remote-access >/dev/null 2>&1; then
        useradd -r -s /bin/false remote-access
        print_info "User 'remote-access' created"
    else
        print_info "User 'remote-access' already exists"
    fi
}

install_application() {
    print_header "Installing Application"
    
    # Create installation directory
    mkdir -p $INSTALL_DIR
    
    # Copy server files
    if [ -f "server/main.py" ]; then
        cp server/main.py $INSTALL_DIR/
        cp server/requirements.txt $INSTALL_DIR/
        print_info "Server files copied"
    else
        print_error "Server files not found. Please run this script from the project root."
        exit 1
    fi
    
    # Create Python virtual environment
    python3 -m venv $INSTALL_DIR/venv
    
    # Install Python dependencies
    $INSTALL_DIR/venv/bin/pip install --upgrade pip
    $INSTALL_DIR/venv/bin/pip install -r $INSTALL_DIR/requirements.txt
    
    # Set permissions
    chown -R remote-access:remote-access $INSTALL_DIR
    chmod 755 $INSTALL_DIR
    
    print_info "Application installed successfully"
}

setup_systemd_service() {
    print_header "Setting up Systemd Service"
    
    cat > /etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=Remote Access Server
After=network.target

[Service]
Type=simple
User=remote-access
Group=remote-access
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/main.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable $SERVICE_NAME
    
    print_info "Systemd service created"
}

setup_nginx() {
    print_header "Configuring Nginx"
    
    # Create web directory
    mkdir -p $WEB_DIR
    
    # Copy web admin files
    if [ -f "web-admin/index.html" ]; then
        cp web-admin/index.html $WEB_DIR/
        chown -R www-data:www-data $WEB_DIR
        print_info "Web admin files copied"
    fi
    
    # Get domain name
    echo -e "${YELLOW}Enter your domain name (or press Enter for localhost):${NC}"
    read -r DOMAIN
    
    if [ -z "$DOMAIN" ]; then
        DOMAIN="localhost"
        SERVER_NAME="_"
    else
        SERVER_NAME="$DOMAIN"
    fi
    
    # Create Nginx configuration
    cat > /etc/nginx/sites-available/remote-access <<EOF
server {
    listen 80;
    server_name $SERVER_NAME;

    # Admin Portal
    location / {
        root $WEB_DIR;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    # API Proxy
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # WebSocket Proxy
    location /ws/ {
        proxy_pass http://localhost:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }
}
EOF

    # Enable site
    ln -sf /etc/nginx/sites-available/remote-access /etc/nginx/sites-enabled/
    
    # Remove default site if exists
    rm -f /etc/nginx/sites-enabled/default
    
    # Test configuration
    nginx -t
    
    # Restart Nginx
    systemctl restart nginx
    
    print_info "Nginx configured successfully"
}

setup_ssl() {
    if [ "$DOMAIN" != "localhost" ] && [ ! -z "$DOMAIN" ]; then
        print_header "Setting up SSL Certificate"
        
        echo -e "${YELLOW}Do you want to set up SSL with Let's Encrypt? (y/n)${NC}"
        read -r SETUP_SSL
        
        if [ "$SETUP_SSL" = "y" ] || [ "$SETUP_SSL" = "Y" ]; then
            certbot --nginx -d $DOMAIN --non-interactive --agree-tos --register-unsafely-without-email
            print_info "SSL certificate installed"
        fi
    fi
}

create_backup_script() {
    print_header "Creating Backup Script"
    
    cat > $INSTALL_DIR/backup.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/opt/remote-access/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
sqlite3 /opt/remote-access/remote_access.db ".backup '$BACKUP_DIR/backup_$DATE.db'"
find $BACKUP_DIR -name "backup_*.db" -mtime +30 -delete
echo "Backup completed: backup_$DATE.db"
EOF

    chmod +x $INSTALL_DIR/backup.sh
    chown remote-access:remote-access $INSTALL_DIR/backup.sh
    
    # Add to crontab
    (crontab -u remote-access -l 2>/dev/null; echo "0 2 * * * $INSTALL_DIR/backup.sh >> /var/log/remote-access-backup.log 2>&1") | crontab -u remote-access -
    
    print_info "Backup script created and scheduled"
}

start_service() {
    print_header "Starting Service"
    
    systemctl start $SERVICE_NAME
    sleep 3
    
    if systemctl is-active --quiet $SERVICE_NAME; then
        print_info "Service started successfully"
    else
        print_error "Service failed to start. Check logs with: journalctl -u $SERVICE_NAME -n 50"
        exit 1
    fi
}

display_summary() {
    print_header "Installation Complete!"
    
    echo ""
    echo -e "${GREEN}Server Status:${NC}"
    systemctl status $SERVICE_NAME --no-pager | head -5
    echo ""
    
    if [ "$DOMAIN" != "localhost" ] && [ ! -z "$DOMAIN" ]; then
        echo -e "${GREEN}Admin Portal:${NC} https://$DOMAIN"
    else
        echo -e "${GREEN}Admin Portal:${NC} http://localhost (or http://$(hostname -I | awk '{print $1}'))"
    fi
    
    echo -e "${GREEN}API Endpoint:${NC} http://localhost:8000"
    echo ""
    echo -e "${YELLOW}Default Credentials:${NC}"
    echo -e "  Email: ${GREEN}admin@localhost${NC}"
    echo -e "  Password: ${GREEN}admin123${NC}"
    echo -e "  ${RED}*** CHANGE PASSWORD IMMEDIATELY! ***${NC}"
    echo ""
    echo -e "${GREEN}Useful Commands:${NC}"
    echo -e "  View logs: ${YELLOW}sudo journalctl -u $SERVICE_NAME -f${NC}"
    echo -e "  Restart service: ${YELLOW}sudo systemctl restart $SERVICE_NAME${NC}"
    echo -e "  Stop service: ${YELLOW}sudo systemctl stop $SERVICE_NAME${NC}"
    echo -e "  Database location: ${YELLOW}$INSTALL_DIR/remote_access.db${NC}"
    echo -e "  Backup script: ${YELLOW}$INSTALL_DIR/backup.sh${NC}"
    echo ""
    echo -e "${GREEN}Next Steps:${NC}"
    echo "1. Login to admin portal"
    echo "2. Change admin password"
    echo "3. Configure SMTP settings"
    echo "4. Create IT member accounts"
    echo "5. Build and distribute Windows client"
    echo ""
}

# Main installation flow
main() {
    print_header "Remote Access System - Automated Deployment"
    
    check_root
    install_dependencies
    setup_firewall
    create_system_user
    install_application
    setup_systemd_service
    setup_nginx
    setup_ssl
    create_backup_script
    start_service
    display_summary
}

# Run main installation
main
