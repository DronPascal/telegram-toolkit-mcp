# Telegram Toolkit MCP - Project Brief

## Project Overview
**Telegram Toolkit MCP** is a read-only Model Context Protocol (MCP) server designed to safely extract message history from public Telegram chats and channels by date periods with paginated delivery (ASC order), strict `structuredContent` according to schema, and large exports via NDJSON resources (MCP rev. 2025-06-18).

## Core Objectives
- Provide secure read-only access to public Telegram channel/group message history
- Support date-range filtering with ascending pagination and cursor-based navigation
- Implement strict JSON Schema validation for all responses
- Handle large datasets via NDJSON resource streaming
- Ensure compatibility with MCP specification rev. 2025-06-18
- Support remote deployment via Streamable HTTP transport

## Key Features
- **Date-based filtering**: Extract messages within specific UTC time ranges
- **Pagination**: Cursor-based navigation with configurable page sizes (≤100)
- **Content filtering**: Server-side filtering by message types (media, links, etc.)
- **Search**: Text-based message search within date ranges
- **Thread support**: Handle forum topics and thread-based conversations
- **Resource streaming**: NDJSON exports for large datasets
- **Error handling**: Comprehensive error codes with retry mechanisms
- **Observability**: Prometheus metrics, OpenTelemetry tracing, structured logging

## Technical Foundation
- **Language**: Python 3.11+
- **Telegram Client**: Telethon (MTProto user-session based)
- **MCP Framework**: Official Python SDK with FastMCP
- **Transport**: Streamable HTTP (Cloudflare compatible)
- **Data Format**: JSON Schema Draft 2020-12, NDJSON for resources
- **Authentication**: StringSession-based user authentication
- **Storage**: In-memory processing with NDJSON file exports

## Success Criteria
- **Performance**: p95 ≤ 2.5s per page (≤100 messages)
- **Accuracy**: 0% gaps in date ranges, ≤0.5% duplicates
- **Reliability**: Proper FLOOD_WAIT handling with cursor preservation
- **Compliance**: Strict adherence to MCP 2025-06-18 specification
- **Security**: No PII logging, secure session management
- **Scalability**: Efficient handling of large public channels (1000+ messages/day)

## Project Scope (v1.0 MVP)
**Included:**
- Core tools: `tg.resolve_chat`, `tg.fetch_history`
- Date-range filtering and pagination
- Content type filtering and text search
- NDJSON resource exports
- Comprehensive error handling
- Basic observability (metrics, tracing, logging)

**Excluded:**
- Message sending or modification
- Binary media downloads
- Private/invite-only chats
- Administrative actions
- Real-time message streaming

## Risk Mitigation
- **API Limits**: Exponential backoff, cursor preservation, rate limiting
- **Data Accuracy**: Server-side date filtering, message deduplication
- **Security**: Secure session storage, PII masking, audit logging
- **Performance**: Resource-based large exports, configurable page sizes
- **Compliance**: MCP specification adherence, public-only access

## Quality Assurance
- **Testing**: Unit tests for schemas, cursors, errors; E2E tests on public channels
- **Validation**: JSON Schema compliance for all responses
- **Monitoring**: SLO tracking, error rate monitoring, performance metrics
- **Documentation**: Comprehensive README, API examples, error code reference

## Future Roadmap
- **v1.1**: Advanced statistics tool (`tg.stats`)
- **v1.2**: Multi-backend support (Pyrogram alternative)
- **v2.0**: Media download capabilities
- **v2.1**: Real-time monitoring features

## Project Status
**Current Phase**: 🎉 **PRODUCTION LIVE & OPERATIONAL** - Enterprise-grade deployment with comprehensive testing
**Latest Achievement**: Complete production infrastructure with Docker + Nginx + SSL + monitoring
**Timeline**: ✅ **COMPLETED** - 8 weeks MVP + 1 day production deployment + comprehensive testing architecture
**Team**: Solo developer with MCP/Telegram expertise
**Production Readiness**: ✅ **100% READY AND OPERATIONAL**
**Current Focus**: User adoption, feature expansion, and community building

## Production Deployment Status - LIVE
**✅ VPS Deployment**: Complete with Docker + Nginx + SSL
**✅ Domain**: your-domain.com configured and live
**✅ SSL Certificate**: Let's Encrypt auto-renewal active
**✅ Health Checks**: All endpoints responding correctly
**✅ MCP Protocol**: JSON-RPC endpoints functional
**✅ Monitoring**: Basic health monitoring active

## 🚀 Production Deployment Status - LIVE AND OPERATIONAL

### **✅ Infrastructure Deployed and Live:**
- **VPS Server**: Ubuntu with Docker + Nginx + SSL ✅
- **HTTP Transport**: FastMCP with `mcp.run(transport="http")` ✅
- **Health Checks**: `/health` endpoint responding ✅
- **Docker Stack**: Production Dockerfile + Compose v2 ✅
- **Nginx Proxy**: Streamable HTTP with `proxy_buffering off` ✅
- **SSL/TLS**: Let's Encrypt certificate active ✅
- **Domain**: your-domain.com configured ✅

### **✅ Production Endpoints Live:**
- **Health Check**: `https://your-domain.com/health` ✅
- **Metrics**: `https://your-domain.com/metrics` ✅
- **MCP API**: `https://your-domain.com/mcp` ✅
- **Tools API**: `https://your-domain.com/api/tools` ✅

### **✅ Enterprise Features Active:**
- **Remote MCP**: Full HTTP streaming support ✅
- **Security**: Enterprise-grade PII protection ✅
- **SSL**: Auto-renewal Let's Encrypt ✅
- **Monitoring**: Health checks and basic monitoring ✅

### **🚀 Current Production Commands:**
```bash
# Test current live deployment
curl https://your-domain.com/health
curl https://your-domain.com/metrics

# MCP protocol test
curl -X POST https://your-domain.com/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'

# Direct FastMCP access
curl http://localhost:8000/health
```

### **🔗 MCP Client Integration:**
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

**PROJECT STATUS: ENTERPRISE PRODUCTION READY** 🎉✨
