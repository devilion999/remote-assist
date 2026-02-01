#!/bin/bash
################################################################################
# Remote Assist - One-Line Installation Script
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/devilion999/remote-assist/main/install.sh | sudo bash
################################################################################

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Remote Assist - Quick Installation${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run with sudo${NC}"
    exit 1
fi

# Install git if not present
if ! command -v git &> /dev/null; then
    echo -e "${GREEN}Installing git...${NC}"
    apt update && apt install -y git
fi

# Clone repository
echo -e "${GREEN}Downloading Remote Assist from GitHub...${NC}"
cd /tmp
rm -rf remote-assist
git clone https://github.com/devilion999/remote-assist.git
cd remote-assist

# Verify files exist
if [ ! -f "server/main.py" ]; then
    echo -e "${RED}Error: Server files not found in repository!${NC}"
    echo -e "${YELLOW}Please check https://github.com/devilion999/remote-assist${NC}"
    exit 1
fi

# Run deployment script
echo -e "${GREEN}Running deployment script...${NC}"
echo ""
bash deploy.sh

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
