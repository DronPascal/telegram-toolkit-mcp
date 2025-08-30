# 🚀 Telegram Toolkit MCP - Production Deployment Guide

## 📋 Overview

### 🔧 Domain Configuration

**Repository contains placeholder domains** for security and privacy:
- `YOUR_DOMAIN_PLACEHOLDER` in `nginx.conf` - automatically replaced during deployment
- `your-domain.com` in examples - replace with your actual domain
- `admin@your-domain.com` in examples - replace with your actual email

### 🚀 Quick Deployment

```bash
# Deploy with your domain
./deploy.sh your-domain.com admin@your-domain.com

# The script will automatically:
# ✅ Replace YOUR_DOMAIN_PLACEHOLDER with your-domain.com
# ✅ Configure Nginx with your domain
# ✅ Set up SSL certificate
# ✅ Start services
```

This guide covers deploying the Telegram Toolkit MCP server to a production VPS with Docker, Nginx reverse proxy, and SSL certificates. The deployment is designed to be secure, scalable, and easy to maintain.

## 🎯 Quick Start

### Prerequisites

- **VPS with root access** (Ubuntu 20.04+ recommended)
- **Domain name** configured in Cloudflare
- **Docker & Docker Compose** installed
- **Telegram API credentials** (from https://my.telegram.org/auth)

### One-Command Deployment

```bash
# Clone the repository
git clone https://github.com/DronPascal/telegram-toolkit-mcp.git
cd telegram-toolkit-mcp

# Run automated deployment
./deploy.sh your-domain.com admin@your-domain.com
```

### 🚀 Remote MCP Features

This deployment supports **Remote MCP** with:
- ✅ **Streamable HTTP** on `/mcp` endpoint
- ✅ **Cloudflare integration** for WAF and DDoS protection
- ✅ **Nginx reverse proxy** with streaming support
- ✅ **SSL/TLS encryption** with automatic certificates
- ✅ **FLOOD_WAIT handling** with cursor resumption
- ✅ **Enterprise monitoring** and observability

## 📦 Manual Deployment Steps

### Step 1: Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Create a new user for running the application (don't run as root)
sudo useradd -m -s /bin/bash telegram-mcp
sudo usermod -aG sudo telegram-mcp
sudo passwd telegram-mcp

# Switch to the new user
su - telegram-mcp

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose v2 (recommended)
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Nginx
sudo apt install nginx -y

# Install Certbot (for SSL)
sudo apt install certbot python3-certbot-nginx -y

# Create deployment directory
sudo mkdir -p /opt/telegram-toolkit-mcp
sudo chown -R $USER:$USER /opt/telegram-toolkit-mcp
```

### Step 2: Configure Domain in Cloudflare

1. **Add DNS Record**:
   - Type: `A`
   - Name: `mcp` (or your preferred subdomain)
   - Content: Your VPS IP address
   - Proxy status: `Proxied` (orange cloud) ✅ **CRITICAL for Remote MCP**

2. **SSL/TLS Settings**:
   - SSL/TLS encryption mode: `Full (strict)`
   - Always Use HTTPS: `On`
   - Minimum TLS Version: `1.2`

3. **🚀 CRITICAL: Streaming Configuration**:
   - **Speed > Optimized**: Select for streaming performance
   - **Rocket Loader**: `Off` (may interfere with streaming)
   - **Auto Minify**: `Off` (may break MCP protocol)
   - **Brotli**: `On` (for compression, but not required)

4. **Security Settings**:
   - **WAF**: `On` (recommended for production)
   - **Rate Limiting**: Configure as needed
   - **DDoS Protection**: `On`

### Step 3: Deploy Application

```bash
# Clone project files to deployment directory
cd /opt/telegram-toolkit-mcp
git clone https://github.com/DronPascal/telegram-toolkit-mcp.git .

# Configure environment
cp env.example .env
nano .env  # Edit with your Telegram API credentials

# Start the application with Docker Compose v2
docker compose up -d
```

### Step 4: Configure Nginx Reverse Proxy

```bash
# Copy nginx configuration
sudo cp nginx.conf /etc/nginx/sites-available/your-domain.com

# Update domain name in config
sudo sed -i 's/YOUR_DOMAIN_PLACEHOLDER/your-domain.com/g' /etc/nginx/sites-available/your-domain.com

# Enable site
sudo ln -s /etc/nginx/sites-available/your-domain.com /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### Step 5: Configure SSL Certificate

```bash
# Get SSL certificate
sudo certbot --nginx -d your-domain.com --email admin@your-domain.com

# Test renewal (certbot creates automatic renewal)
sudo certbot renew --dry-run
```

## 🔧 Configuration

### Environment Variables

Edit `.env` file with your configuration:

```bash
# Required
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# Optional
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8000
MAX_PAGE_SIZE=100
DEBUG=false
```

### Docker Compose Profiles

```bash
# Basic deployment (recommended)
docker compose up -d

# With observability stack
docker compose --profile observability up -d

# Development mode
docker compose -f docker-compose.dev.yml up -d
```

## 🔍 Monitoring & Troubleshooting

### Health Checks

```bash
# Check application health
curl https://your-domain.com/health

# Check metrics
curl https://your-domain.com/metrics
```

### Logs

```bash
# Application logs
docker compose logs -f telegram-mcp

# Nginx logs
sudo tail -f /var/log/nginx/telegram-mcp.access.log
sudo tail -f /var/log/nginx/telegram-mcp.error.log
```

### Common Issues

#### 1. Telegram API Credentials Error
```
❌ Error: Invalid Telegram API credentials
✅ Solution: Double-check TELEGRAM_API_ID and TELEGRAM_API_HASH in .env
```

#### 2. SSL Certificate Issues
```
❌ Error: SSL certificate validation failed
✅ Solution: Run `sudo certbot --nginx -d your-domain.com`
```

#### 3. Port Already in Use
```
❌ Error: Port 8000 already in use
✅ Solution: Change MCP_SERVER_PORT in .env or stop conflicting service
```

#### 4. Domain Not Resolving
```
❌ Error: DNS resolution failed
✅ Solution: Check Cloudflare DNS settings and wait for propagation (up to 24h)
```

#### 5. MCP Streaming Issues
```
❌ Error: Connection timeout or broken streaming
✅ Solution: Check nginx.conf has proxy_buffering off for /mcp endpoint
```

#### 6. Cloudflare Streaming Problems
```
❌ Error: Response not streaming properly
✅ Solution: Disable Rocket Loader and Auto Minify in Cloudflare
```

#### 7. FLOOD_WAIT Handling
```
❌ Error: Server stops responding during rate limits
✅ Solution: Check logs for FLOOD_WAIT, server should resume automatically
```

## 🔒 Security Best Practices

### 1. Network Security
- Use Cloudflare as WAF and DDoS protection
- Restrict SSH access with fail2ban
- Use non-standard SSH port

### 2. Application Security
- Keep dependencies updated
- Use strong Telegram API credentials
- Enable rate limiting in production

### 3. SSL/TLS Security
- Use only TLS 1.2+ protocols
- Configure HSTS headers
- Regular certificate renewal

## 📊 Performance Optimization

### Docker Optimization

```yaml
# docker-compose.yml optimizations
services:
  telegram-mcp:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'
```

### Nginx Optimization

```nginx
# nginx.conf optimizations
worker_processes auto;
worker_connections 1024;

# Enable gzip compression
gzip on;
gzip_types text/plain application/json application/javascript;

# Cache static assets
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### Monitoring Setup

```bash
# Enable observability stack
docker compose --profile observability up -d

# Access monitoring
# Grafana: http://your-server:3000 (admin/admin)
# Prometheus: http://your-server:9090
# Jaeger: http://your-server:16686
```

## 🔄 Updates & Maintenance

### Application Updates

```bash
# Update application
cd /opt/telegram-toolkit-mcp
git pull
docker compose build --no-cache
docker compose up -d

# Check health after update
curl https://your-domain.com/health
```

### SSL Certificate Renewal

```bash
# Automatic renewal (runs twice daily)
sudo systemctl status certbot.timer

# Manual renewal
sudo certbot renew
```

### Backup Strategy

```bash
# Backup important data
tar -czf backup-$(date +%Y%m%d).tar.gz \
    /opt/telegram-toolkit-mcp/.env \
    /opt/telegram-toolkit-mcp/data/ \
    /etc/nginx/sites-available/your-domain.com
```

## 🌐 Integration with MCP Clients

### 🚀 Remote MCP Configuration

Your server supports **Remote MCP** with Streamable HTTP on `/mcp` endpoint.

### Claude Desktop Configuration

```json
{
  "mcpServers": {
    "telegram-toolkit": {
      "command": "npx",
      "args": ["@modelcontextprotocol/inspector", "--remote", "https://your-domain.com/mcp"]
    }
  }
}
```

### MCP Inspector (for testing)

```bash
# Install MCP Inspector
npm install -g @modelcontextprotocol/inspector

# Test connection
npx @modelcontextprotocol/inspector --remote https://your-domain.com/mcp

# Or use direct HTTP endpoint
curl -X POST https://your-domain.com/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

### Other MCP Clients

```bash
# Direct HTTP connection to tools
curl -X POST https://your-domain.com/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "tg.resolve_chat",
      "arguments": {"input": "@telegram"}
    }
  }'

# Test resources
curl -X POST https://your-domain.com/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "resources/list"}'
```

### 🔧 Remote MCP Endpoints

- **Main MCP endpoint**: `https://your-domain.com/mcp`
- **Health check**: `https://your-domain.com/health`
- **Metrics**: `https://your-domain.com/metrics` (if enabled)
- **Legacy API**: `https://your-domain.com/tools/call` (deprecated)

## 📞 Support & Troubleshooting

### Getting Help

1. **Check Logs**: `docker compose logs -f`
2. **Health Check**: `curl https://your-domain.com/health`
3. **Metrics**: `curl https://your-domain.com/metrics`

### Common Support Scenarios

#### Telegram API Issues
- Verify API credentials are correct
- Check Telegram API status
- Ensure you're not rate-limited

#### Network Issues
- Check DNS resolution
- Verify firewall settings
- Test connectivity from different locations

#### Performance Issues
- Monitor resource usage
- Check application metrics
- Review Nginx access logs

## 🎯 Success Checklist

- [ ] ✅ Domain configured in Cloudflare
- [ ] ✅ SSL certificate installed
- [ ] ✅ Docker containers running
- [ ] ✅ Nginx proxy configured
- [ ] ✅ Health checks passing
- [ ] ✅ MCP client integration tested
- [ ] ✅ Monitoring configured
- [ ] ✅ Backup strategy in place

## 🚀 Production URLs

After successful deployment:

### Remote MCP Endpoints
- **Main MCP endpoint**: `https://your-domain.com/mcp` 🚀 **PRIMARY**
- **Legacy API**: `https://your-domain.com/tools/call` (deprecated)

### Monitoring & Health
- **Health Check**: `https://your-domain.com/health`
- **Metrics**: `https://your-domain.com/metrics`
- **Logs**: `docker-compose logs -f telegram-mcp`

### Testing Commands
```bash
# Test MCP connection
curl -X POST https://your-domain.com/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'

# Test with MCP Inspector
npx @modelcontextprotocol/inspector --remote https://your-domain.com/mcp
```

## 🎯 Remote MCP Checklist

- [ ] ✅ **Streamable HTTP** configured (`/mcp` endpoint)
- [ ] ✅ **Cloudflare proxy** enabled (orange cloud)
- [ ] ✅ **Nginx buffering** disabled for `/mcp`
- [ ] ✅ **SSL certificate** installed
- [ ] ✅ **FLOOD_WAIT handling** working
- [ ] ✅ **MCP Inspector** connection tested
- [ ] ✅ **Telegram credentials** configured
- [ ] ✅ **Resource volumes** mounted
- [ ] ✅ **Health checks** passing

---

**🎉 Your Telegram Toolkit MCP server is now ENTERPRISE PRODUCTION READY!**

**🚀 Ready for Remote MCP clients with full streaming support!**

Need help? Check the [GitHub Issues](https://github.com/DronPascal/telegram-toolkit-mcp/issues) or create a new issue.
