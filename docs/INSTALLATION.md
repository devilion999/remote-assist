# Remote Access System - Installation & Deployment Guide

## Overview

This remote access system provides TeamViewer-like functionality with:
- Linux-based server infrastructure
- Web-based admin portal for IT management
- Windows client application for customers
- UDP-based real-time screen streaming
- User management with SMTP notifications
- Session management (up to 10 concurrent sessions per user)

## System Architecture

```
┌─────────────────┐         UDP          ┌──────────────────┐
│ Windows Client  │◄─────────────────────►│  Linux Server    │
│  (Customer)     │                       │  (Port 50000+)   │
└─────────────────┘                       └──────────────────┘
                                                    ▲
                                                    │
                                            REST API (Port 8000)
                                                    │
                                                    ▼
                                          ┌──────────────────┐
                                          │  Web Admin       │
                                          │  (IT Members)    │
                                          └──────────────────┘
```

## Prerequisites

### Server Requirements
- **OS**: Ubuntu 20.04 LTS or later / Debian 11+
- **RAM**: Minimum 2GB, Recommended 4GB+
- **CPU**: 2+ cores
- **Storage**: 20GB+ available
- **Network**: Static IP or domain name
- **Ports**: 
  - 8000 (API/WebSocket)
  - 50000-60000 (UDP for sessions)

### Client Requirements
- **OS**: Windows 10/11 (64-bit)
- **.NET**: .NET 6.0 Runtime or later
- **Network**: Outbound UDP access

## Server Installation

### 1. System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.10+
sudo apt install python3 python3-pip python3-venv -y

# Install required system packages
sudo apt install sqlite3 libsqlite3-dev build-essential -y
```

### 2. Create Application Directory

```bash
# Create app directory
sudo mkdir -p /opt/remote-access
sudo chown $USER:$USER /opt/remote-access
cd /opt/remote-access

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Server Application

```bash
# Copy server files to /opt/remote-access/
# main.py
# requirements.txt

# Install dependencies
pip install -r requirements.txt

# Initialize database
python3 main.py &
sleep 5
pkill -f "python3 main.py"
```

### 4. Configure Firewall

```bash
# Allow API port
sudo ufw allow 8000/tcp

# Allow UDP range for sessions
sudo ufw allow 50000:60000/udp

# Enable firewall if not already enabled
sudo ufw --force enable
```

### 5. Create Systemd Service

Create `/etc/systemd/system/remote-access.service`:

```ini
[Unit]
Description=Remote Access Server
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/remote-access
Environment="PATH=/opt/remote-access/venv/bin"
ExecStart=/opt/remote-access/venv/bin/python3 main.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
# Create service file
sudo nano /etc/systemd/system/remote-access.service
# Paste content above

# Set permissions
sudo chown www-data:www-data /opt/remote-access
sudo chmod 755 /opt/remote-access

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable remote-access
sudo systemctl start remote-access

# Check status
sudo systemctl status remote-access
```

### 6. Setup Nginx Reverse Proxy (Optional but Recommended)

```bash
# Install Nginx
sudo apt install nginx -y

# Create Nginx configuration
sudo nano /etc/nginx/sites-available/remote-access
```

Add the following configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Admin Portal
    location / {
        root /opt/remote-access/web-admin;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # API Proxy
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket Proxy
    location /ws/ {
        proxy_pass http://localhost:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

Enable the site:

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/remote-access /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

### 7. Setup SSL with Let's Encrypt (Recommended)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is configured automatically
```

## Web Admin Setup

### 1. Deploy Admin Portal

```bash
# Copy web-admin files
sudo mkdir -p /opt/remote-access/web-admin
sudo cp index.html /opt/remote-access/web-admin/

# Update API URL in index.html
sudo nano /opt/remote-access/web-admin/index.html
# Change: const API_URL = 'http://localhost:8000/api';
# To: const API_URL = 'https://your-domain.com/api';
```

### 2. Access Admin Portal

1. Navigate to `https://your-domain.com`
2. Login with default credentials:
   - **Email**: `admin@localhost`
   - **Password**: `admin123`
3. **IMPORTANT**: Change the admin password immediately!

### 3. Configure SMTP

Navigate to **SMTP Config** tab and configure email settings.

#### For Microsoft 365:

```
SMTP Host: smtp.office365.com
SMTP Port: 587
Security Type: TLS/STARTTLS
Username: your-email@yourdomain.com
Password: [Your password or app password]
From Email: noreply@yourdomain.com
Require Auth: ✓ Checked
```

#### For Gmail:

```
SMTP Host: smtp.gmail.com
SMTP Port: 587
Security Type: TLS/STARTTLS
Username: your-email@gmail.com
Password: [App-specific password]
From Email: your-email@gmail.com
Require Auth: ✓ Checked
```

**Note**: For Gmail, you must create an "App Password" in your Google Account settings.

#### For SendGrid:

```
SMTP Host: smtp.sendgrid.net
SMTP Port: 587
Security Type: TLS/STARTTLS
Username: apikey
Password: [Your SendGrid API Key]
From Email: verified-sender@yourdomain.com
Require Auth: ✓ Checked
```

## Windows Client Setup

### 1. Build the Client

On a Windows development machine:

```powershell
# Install .NET SDK if not already installed
# Download from: https://dotnet.microsoft.com/download

# Navigate to client directory
cd windows-client

# Update SERVER_URL in RemoteAccessClient.cs
# Change: private const string SERVER_URL = "http://your-server-address:8000";
# To: private const string SERVER_URL = "https://your-domain.com";

# Build the application
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true

# The executable will be in: bin\Release\net6.0-windows\win-x64\publish\
```

### 2. Distribute to Customers

Create an installer or provide the executable:

```powershell
# The client executable is standalone and portable
# Copy from: bin\Release\net6.0-windows\win-x64\publish\RemoteAccessClient.exe

# Optionally create an installer using:
# - Inno Setup
# - WiX Toolset
# - Advanced Installer
```

### 3. Client Usage Instructions

1. Run `RemoteAccessClient.exe`
2. Enter the 9-digit session code provided by IT support
3. Click "Connect"
4. The client will automatically connect and share the screen

## User Management

### Adding IT Members

1. Login to admin portal as administrator
2. Navigate to **Users** tab
3. Click **+ Add User**
4. Fill in the form:
   - Full Name
   - Email
   - Password (min 8 characters)
   - Role (Admin or IT Technician)
   - Max Concurrent Sessions (1-50)
5. Click **Create User**

The user will receive an email with login credentials.

### User Roles

**Administrator**:
- Full access to all features
- Can create/manage users
- Can configure SMTP settings
- Can view all sessions
- Unlimited session creation

**IT Technician**:
- Can create sessions (up to configured limit)
- Can view own sessions only
- Cannot create users or configure SMTP

## Session Management

### Creating a New Session

1. Click **+ New Session**
2. Optionally enter:
   - Customer Name
   - Customer Email (will receive session code via email)
3. Click **Create Session**
4. Share the 9-digit session code with the customer

### Session Limits

Each IT member can have up to their configured maximum concurrent sessions (default: 10).

### Closing Sessions

Sessions can be closed:
- Manually by clicking "Close" in the admin portal
- Automatically when customer disconnects
- Automatically after timeout (configurable in code)

## Monitoring and Logs

### View Server Logs

```bash
# View real-time logs
sudo journalctl -u remote-access -f

# View recent logs
sudo journalctl -u remote-access -n 100

# View logs for specific date
sudo journalctl -u remote-access --since "2024-01-01" --until "2024-01-02"
```

### Database Access

```bash
# Access database
cd /opt/remote-access
sqlite3 remote_access.db

# View sessions
SELECT * FROM sessions ORDER BY created_at DESC LIMIT 10;

# View users
SELECT email, full_name, role, is_active FROM users;

# Exit
.quit
```

## Security Recommendations

### 1. Change Default Admin Password

```sql
-- Connect to database
sqlite3 /opt/remote-access/remote_access.db

-- Update admin password (replace 'newhash' with SHA256 of new password)
UPDATE users 
SET password_hash = 'YOUR_NEW_PASSWORD_HASH_HERE' 
WHERE email = 'admin@localhost';
```

Generate new hash in Python:
```python
import hashlib
password = "your_new_password"
hash = hashlib.sha256(password.encode()).hexdigest()
print(hash)
```

### 2. Enable HTTPS Only

Ensure SSL is properly configured and force HTTPS redirects in Nginx.

### 3. Configure Firewall Rules

```bash
# Only allow necessary ports
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 50000:60000/udp
sudo ufw enable
```

### 4. Regular Updates

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Python packages
cd /opt/remote-access
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt --upgrade
```

### 5. Implement Rate Limiting

Consider adding rate limiting in Nginx:

```nginx
# Add to nginx.conf http block
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

# Add to location /api/ block
limit_req zone=api_limit burst=20 nodelay;
```

## Backup and Recovery

### Backup Database

```bash
# Create backup script
cat > /opt/remote-access/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/remote-access/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
sqlite3 /opt/remote-access/remote_access.db ".backup '$BACKUP_DIR/backup_$DATE.db'"
# Keep only last 30 days
find $BACKUP_DIR -name "backup_*.db" -mtime +30 -delete
EOF

chmod +x /opt/remote-access/backup.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/remote-access/backup.sh") | crontab -
```

### Restore Database

```bash
# Stop service
sudo systemctl stop remote-access

# Restore from backup
cp /opt/remote-access/backups/backup_YYYYMMDD_HHMMSS.db /opt/remote-access/remote_access.db

# Start service
sudo systemctl start remote-access
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
sudo journalctl -u remote-access -n 50

# Check if port is in use
sudo netstat -tulpn | grep 8000

# Verify Python environment
cd /opt/remote-access
source venv/bin/activate
python3 main.py
```

### Client Can't Connect

1. Verify server is running: `sudo systemctl status remote-access`
2. Check firewall: `sudo ufw status`
3. Verify UDP ports are open
4. Check session code is valid
5. Verify SERVER_URL in client matches server address

### Email Not Sending

1. Verify SMTP configuration in admin portal
2. Test SMTP settings manually
3. Check for firewall blocking outbound SMTP ports
4. Verify authentication credentials are correct

### High Resource Usage

```bash
# Check resource usage
top
htop

# Check number of active sessions
sqlite3 /opt/remote-access/remote_access.db "SELECT COUNT(*) FROM sessions WHERE status='active';"

# Adjust worker count in main.py if needed
# Change: workers=4 to workers=2
```

## Performance Tuning

### Optimize UDP Buffer Sizes

```bash
# Increase UDP buffer sizes
sudo sysctl -w net.core.rmem_max=26214400
sudo sysctl -w net.core.rmem_default=26214400
sudo sysctl -w net.core.wmem_max=26214400
sudo sysctl -w net.core.wmem_default=26214400

# Make permanent
echo "net.core.rmem_max=26214400" | sudo tee -a /etc/sysctl.conf
echo "net.core.rmem_default=26214400" | sudo tee -a /etc/sysctl.conf
echo "net.core.wmem_max=26214400" | sudo tee -a /etc/sysctl.conf
echo "net.core.wmem_default=26214400" | sudo tee -a /etc/sysctl.conf
```

### Adjust Worker Count

Edit `/etc/systemd/system/remote-access.service` and modify the ExecStart line to include worker configuration based on CPU cores.

## Scaling

For high-volume deployments:

1. **Load Balancer**: Use HAProxy or Nginx for API load balancing
2. **Database**: Migrate from SQLite to PostgreSQL
3. **Horizontal Scaling**: Deploy multiple server instances
4. **Session Affinity**: Implement sticky sessions for UDP connections

## Support

For technical support:
- Email: support@yourcompany.com
- Documentation: https://docs.yourcompany.com
- Issue Tracker: https://github.com/yourcompany/remote-access

## License

[Your License Here]

---

**Version**: 1.0.0  
**Last Updated**: January 2026
