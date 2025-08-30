#!/bin/bash
# Telegram Toolkit MCP - Automated Deployment Script
# This script deploys the MCP server to a VPS with Docker and Nginx

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOMAIN_NAME=${1:-"your-domain.com"}
EMAIL=${2:-"admin@your-domain.com"}
DEPLOY_PATH="/opt/telegram-toolkit-mcp"

echo -e "${BLUE}🚀 Telegram Toolkit MCP Deployment Script${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "${BLUE}Domain: $DOMAIN_NAME${NC}"
echo -e "${BLUE}Email: $EMAIL${NC}"
echo ""

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}❌ This script should not be run as root${NC}"
   exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check if Docker Compose is installed (v2)
if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose v2 is not installed. Please install Docker Compose v2 first.${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 Pre-deployment checks...${NC}"

# Create deployment directory
echo -e "${BLUE}📁 Creating deployment directory...${NC}"
sudo mkdir -p $DEPLOY_PATH
sudo chown -R $USER:$USER $DEPLOY_PATH

# Copy project files
echo -e "${BLUE}📋 Copying project files...${NC}"
if [ -d "$DEPLOY_PATH/.git" ]; then
    echo -e "${YELLOW}⚠️  Deployment directory already exists. Pulling latest changes...${NC}"
    cd $DEPLOY_PATH
    git pull origin main
else
    cp -r . $DEPLOY_PATH/
    cd $DEPLOY_PATH
fi

# Create environment file
echo -e "${BLUE}⚙️ Setting up environment configuration...${NC}"
if [ ! -f .env ]; then
    cp env.example .env
    echo -e "${YELLOW}⚠️ Please edit .env file with your Telegram API credentials${NC}"
    echo -e "${YELLOW}   Required: TELEGRAM_API_ID, TELEGRAM_API_HASH${NC}"
fi

# Create data directories
echo -e "${BLUE}📁 Creating data directories...${NC}"
mkdir -p data resources logs

# Build Docker image
echo -e "${BLUE}🐳 Building Docker image...${NC}"
docker compose build

# Start services (without observability first)
echo -e "${BLUE}🚀 Starting MCP server...${NC}"
docker compose up -d telegram-mcp

# Wait for service to be healthy
echo -e "${BLUE}⏳ Waiting for service to be healthy...${NC}"
sleep 30

# Check if service is running
if docker compose ps | grep -q "Up"; then
    echo -e "${GREEN}✅ MCP server is running!${NC}"
else
    echo -e "${RED}❌ MCP server failed to start${NC}"
    docker compose logs telegram-mcp
    exit 1
fi

# Configure Nginx (if available)
if command -v nginx &> /dev/null; then
    echo -e "${BLUE}🌐 Configuring Nginx...${NC}"

    # Copy nginx config
    sudo cp nginx.conf /etc/nginx/sites-available/$DOMAIN_NAME
    sudo ln -sf /etc/nginx/sites-available/$DOMAIN_NAME /etc/nginx/sites-enabled/

    # Update nginx config with actual domain
    echo -e "${YELLOW}🔧 Replacing YOUR_DOMAIN_PLACEHOLDER with $DOMAIN_NAME...${NC}"
    sudo sed -i "s/YOUR_DOMAIN_PLACEHOLDER/$DOMAIN_NAME/g" /etc/nginx/sites-available/$DOMAIN_NAME

    # Verify replacement worked
    if sudo grep -q "$DOMAIN_NAME" /etc/nginx/sites-available/$DOMAIN_NAME; then
        echo -e "${GREEN}✅ Domain replacement successful${NC}"
    else
        echo -e "${RED}❌ Domain replacement failed${NC}"
        exit 1
    fi

    # Test nginx configuration
    sudo nginx -t

    if [ $? -eq 0 ]; then
        sudo systemctl reload nginx
        echo -e "${GREEN}✅ Nginx configured successfully${NC}"
    else
        echo -e "${RED}❌ Nginx configuration error${NC}"
    fi
else
    echo -e "${YELLOW}⚠️ Nginx not found. Skipping reverse proxy setup.${NC}"
fi

# Configure SSL with Let's Encrypt (if certbot is available)
if command -v certbot &> /dev/null; then
    echo -e "${BLUE}🔒 Setting up SSL certificate...${NC}"

    sudo certbot --nginx -d $DOMAIN_NAME --email $EMAIL --agree-tos --non-interactive

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ SSL certificate installed${NC}"
    else
        echo -e "${RED}❌ SSL certificate installation failed${NC}"
    fi
else
    echo -e "${YELLOW}⚠️ Certbot not found. Skipping SSL setup.${NC}"
    echo -e "${YELLOW}   You can manually configure SSL later.${NC}"
fi

# Show deployment information
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "${GREEN}📍 Your MCP server is now running at:${NC}"
echo -e "${GREEN}   HTTP:  http://$DOMAIN_NAME${NC}"
echo -e "${GREEN}   HTTPS: https://$DOMAIN_NAME${NC}"
echo -e "${GREEN}   Local: http://localhost:8000${NC}"
echo ""

echo -e "${BLUE}🔧 Next steps:${NC}"
echo -e "${YELLOW}1. Edit $DEPLOY_PATH/.env with your Telegram API credentials${NC}"
echo -e "${YELLOW}2. Restart the service: cd $DEPLOY_PATH && docker compose restart${NC}"
echo -e "${YELLOW}3. Check logs: docker compose logs -f${NC}"
echo -e "${YELLOW}4. Test the API: curl https://$DOMAIN_NAME/health${NC}"
echo ""

echo -e "${BLUE}📊 Useful commands:${NC}"
echo -e "${YELLOW}• View logs: docker compose logs -f telegram-mcp${NC}"
echo -e "${YELLOW}• Restart: docker compose restart telegram-mcp${NC}"
echo -e "${YELLOW}• Stop: docker compose down${NC}"
echo -e "${YELLOW}• Update: git pull && docker compose build --no-cache && docker compose up -d${NC}"
echo ""

echo -e "${BLUE}🔍 Monitoring:${NC}"
echo -e "${YELLOW}• Health check: https://$DOMAIN_NAME/health${NC}"
echo -e "${YELLOW}• Metrics: https://$DOMAIN_NAME/metrics${NC}"
echo ""

echo -e "${GREEN}🎯 Ready to serve MCP clients! 🚀${NC}"
