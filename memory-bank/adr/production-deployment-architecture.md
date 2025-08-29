# ADR: Production Deployment Architecture

## Status
**✅ ACCEPTED** - Implemented and Live

## Context
The Telegram Toolkit MCP project needed a robust, scalable production deployment strategy that could handle:
- Remote MCP client connections via HTTP transport
- Enterprise-grade security and monitoring
- High availability and fault tolerance
- SSL/TLS encryption for all communications
- Easy maintenance and updates

## Decision
We chose a containerized deployment architecture using Docker + Nginx + SSL with the following components:

### Infrastructure Stack
1. **VPS Server**: Ubuntu with Docker runtime
2. **Container Orchestration**: Docker Compose v2
3. **Reverse Proxy**: Nginx with streamable HTTP support
4. **SSL Termination**: Let's Encrypt with auto-renewal
5. **Application**: FastMCP in Docker container
6. **Domain**: Custom domain with DNS configuration

### Architecture Diagram
```
Internet → Domain (your-domain.com)
    ↓ HTTPS (443)
Nginx (SSL Termination + Reverse Proxy)
    ↓ HTTP (80) localhost
Docker Container (FastMCP on port 8000)
    ↓ Internal HTTP
FastMCP Application (Python + MCP SDK)
```

## Implementation Details

### Docker Configuration
```yaml
# docker-compose.yml
services:
  telegram-mcp:
    build: .
    ports:
      - "0.0.0.0:8000:8000"  # Bind to all interfaces
    environment:
      - MCP_SERVER_HOST=0.0.0.0  # Listen on all interfaces
      - MCP_SERVER_PORT=8000
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8000/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped
```

### Nginx Configuration
```nginx
# /etc/nginx/sites-available/your-domain.com
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL Configuration (managed by Certbot)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # Health endpoint (normal buffering)
    location /health {
        proxy_pass http://localhost:8000/health;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        access_log off;
        proxy_buffering on;
        proxy_read_timeout 10s;
    }

    # Metrics endpoint (normal buffering)
    location /metrics {
        proxy_pass http://localhost:8000/metrics;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering on;
        proxy_read_timeout 30s;
    }

    # MCP endpoint (streamable HTTP)
    location /mcp {
        proxy_pass http://localhost:8000/mcp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE-specific headers
        proxy_set_header Accept "text/event-stream";
        proxy_set_header Cache-Control "no-cache";
        proxy_set_header Connection "keep-alive";

        # Critical: Disable buffering for streaming
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;

        # Connection upgrade support
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # Other endpoints
    location /api/tools {
        proxy_pass http://localhost:8000/api/tools;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering on;
        proxy_read_timeout 30s;
    }

    # Main application
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering on;
        proxy_read_timeout 30s;
    }
}

# HTTP redirect to HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### FastMCP Application Configuration
```python
# Environment variables in container
MCP_SERVER_HOST=0.0.0.0  # Listen on all interfaces
MCP_SERVER_PORT=8000     # Standard HTTP port
MCP_SERVER_LOG_LEVEL=INFO

# FastMCP server startup
mcp = FastMCP("Telegram History Exporter")

# Get ASGI app for uvicorn
if hasattr(mcp, 'streamable_http_app'):
    asgi_app = mcp.streamable_http_app
else:
    # Fallback logic for older versions
    asgi_app = getattr(mcp, 'app', None)

# Start with uvicorn
uvicorn.run(
    asgi_app,
    host="0.0.0.0",  # Listen on all interfaces
    port=8000,
    log_level="info"
)
```

## Consequences

### Positive
- **Remote MCP Support**: HTTP transport allows remote MCP clients
- **Security**: SSL/TLS encryption for all communications
- **Scalability**: Nginx can handle load balancing and rate limiting
- **Monitoring**: Health checks and metrics exposed via standard endpoints
- **Reliability**: Docker health checks ensure container stability
- **Maintenance**: Easy updates via Docker Compose

### Negative
- **Complexity**: Additional Nginx layer increases deployment complexity
- **Resource Usage**: Extra container (Nginx) consumes resources
- **SSL Management**: Certificate renewal requires automation
- **Network Configuration**: Requires proper port binding and firewall rules

### Risks
- **SSL Certificate Expiry**: Automated renewal mitigates this
- **Nginx Configuration**: Template-based config reduces errors
- **Container Networking**: Docker networking is well-established
- **Performance Overhead**: Nginx proxy has minimal overhead

## Alternatives Considered

### 1. Direct Container Exposure
**Rejected**: Exposing container directly would require SSL termination in container

### 2. Kubernetes Deployment
**Postponed**: Overkill for current scale, can be added later

### 3. Cloud Load Balancer
**Rejected**: VPS deployment with Nginx is sufficient and cost-effective

### 4. Built-in SSL in FastMCP
**Not Available**: FastMCP doesn't support SSL directly, requires reverse proxy

## Implementation Status
**✅ COMPLETED** - Live production deployment on August 29, 2025

### Live Endpoints
- `https://your-domain.com/health` ✅
- `https://your-domain.com/metrics` ✅
- `https://your-domain.com/mcp` ✅
- `https://your-domain.com/api/tools` ✅

### Infrastructure Health
- **SSL Certificate**: Valid until November 27, 2025
- **Domain**: your-domain.com resolving correctly
- **Container**: Healthy with proper resource usage
- **Nginx**: Active with correct configuration
- **Monitoring**: Health checks responding

## Future Considerations

### Scaling
- Add Redis for session management if needed
- Implement horizontal scaling with load balancer
- Add database for caching frequently accessed data

### Security Enhancements
- Implement rate limiting at Nginx level
- Add WAF (Web Application Firewall)
- Enable HSTS headers
- Implement API key authentication

### Monitoring Improvements
- Add comprehensive logging aggregation
- Implement alerting for health check failures
- Add performance monitoring dashboards
- Enable distributed tracing

## References
- [FastMCP HTTP Transport Documentation](https://fastmcp.com/http-transport)
- [Nginx Reverse Proxy Configuration](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
- [Docker Compose Production Guide](https://docs.docker.com/compose/production/)
- [Let's Encrypt Automation](https://certbot.eff.org/docs/)
