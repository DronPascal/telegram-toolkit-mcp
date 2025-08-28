# OpenTelemetry Distributed Tracing

This document describes the comprehensive distributed tracing implementation for the Telegram Toolkit MCP server using OpenTelemetry.

## Overview

Distributed tracing provides end-to-end observability of requests flowing from MCP clients through the server to Telegram API calls. The implementation includes:

- **MCP Tool Tracing**: Complete request lifecycle tracking
- **Telegram API Tracing**: Client-server API call monitoring
- **Resource Operation Tracing**: NDJSON export and management
- **Error Tracing**: Exception propagation and context
- **Performance Monitoring**: Latency and throughput metrics

## Architecture

### Tracing Components

```
MCP Client → FastAPI → MCP Tool → Telegram Client → Telegram API
     ↓          ↓         ↓          ↓            ↓
   Trace     Trace    Trace      Trace        Trace
```

### Span Hierarchy

```
┌─ mcp.tool.tg.resolve_chat (SERVER)
│  ├─ telegram.api.get_chat_info (CLIENT)
│  │  ├─ telethon.api.call (INTERNAL)
│  │  └─ response_processing (INTERNAL)
│  └─ response_formatting (INTERNAL)
│
└─ mcp.tool.tg.fetch_history (SERVER)
   ├─ telegram.api.fetch_messages (CLIENT)
   │  ├─ telethon.api.call (INTERNAL)
   │  ├─ message_processing (INTERNAL)
   │  └─ pagination_logic (INTERNAL)
   └─ resource.create (INTERNAL)
      └─ ndjson_export (INTERNAL)
```

## Configuration

### Environment Variables

```bash
# Enable/disable tracing
ENABLE_OPENTELEMETRY_TRACING=true

# OTLP exporter configuration
OTLP_ENDPOINT=http://localhost:4318
OTLP_EXPORTER=grpc  # grpc, http, jaeger

# Service identification
SERVICE_NAME=telegram-toolkit-mcp
SERVICE_VERSION=1.0.0

# Sampling and limits
TRACE_SAMPLING_RATE=1.0  # 0.0-1.0 (1.0 = 100% sampling)
TRACE_MAX_ATTRIBUTES=128
TRACE_MAX_EVENTS=128
```

### Exporter Options

#### OTLP gRPC (Default)
```bash
OTLP_EXPORTER=grpc
OTLP_ENDPOINT=localhost:4317
```

#### OTLP HTTP
```bash
OTLP_EXPORTER=http
OTLP_ENDPOINT=http://localhost:4318/v1/traces
```

#### Jaeger
```bash
OTLP_EXPORTER=jaeger
OTLP_ENDPOINT=localhost:14268
```

## Span Types and Attributes

### MCP Tool Spans

#### `mcp.tool.tg.resolve_chat`
```json
{
  "span.kind": "SERVER",
  "mcp.tool.name": "tg.resolve_chat",
  "mcp.tool.args_count": 1,
  "mcp.tool.arg.input": "@telegram",
  "chat.input": "@telegram",
  "function.module": "telegram_toolkit_mcp.tools.resolve_chat",
  "function.name": "resolve_chat_tool"
}
```

#### `mcp.tool.tg.fetch_history`
```json
{
  "span.kind": "SERVER",
  "mcp.tool.name": "tg.fetch_history",
  "mcp.tool.args_count": 3,
  "chat.identifier": "@telegram",
  "page_size": 50,
  "has_cursor": false,
  "has_search": false,
  "has_filter": true,
  "direction": "desc"
}
```

### Telegram API Spans

#### `telegram.api.get_chat_info`
```json
{
  "span.kind": "CLIENT",
  "telegram.api.method": "get_chat_info",
  "telegram.api.has_chat": true,
  "telegram.chat.canonical": "@telegram",
  "duration_seconds": 0.234
}
```

#### `telegram.api.fetch_messages`
```json
{
  "span.kind": "CLIENT",
  "telegram.api.method": "fetch_messages",
  "telegram.api.limit": 50,
  "telegram.chat": "@telegram",
  "telegram.limit": 50,
  "telegram.offset_id": 0,
  "messages_count": 50
}
```

### Resource Operation Spans

#### `resource.create`
```json
{
  "span.kind": "INTERNAL",
  "resource.operation": "create",
  "resource.uri": "ndjson_export",
  "resource.messages_count": 150,
  "resource.chat": "@telegram"
}
```

## Events and Exceptions

### Span Events

```json
[
  {
    "name": "tool_started",
    "timestamp": 1640995200000000000,
    "attributes": {
      "tool": "tg.resolve_chat"
    }
  },
  {
    "name": "telegram_api_call_started",
    "timestamp": 1640995200234000000,
    "attributes": {
      "method": "get_chat_info"
    }
  },
  {
    "name": "telegram_api_call_completed",
    "timestamp": 1640995200345000000,
    "attributes": {
      "success": true
    }
  }
]
```

### Exception Recording

```json
{
  "exception.type": "FloodWaitException",
  "exception.message": "Rate limit exceeded",
  "exception.stacktrace": "...",
  "telegram.retry_after": 30,
  "telegram.chat": "@telegram"
}
```

## Tracing Integration

### Automatic Tracing

The system automatically traces:

1. **All MCP tool calls** with input parameters
2. **All Telegram API calls** with request details
3. **All resource operations** with metadata
4. **All exceptions** with context and stack traces
5. **All performance metrics** with timing data

### Manual Tracing

For custom tracing in new code:

```python
from telegram_toolkit_mcp.core.tracing import (
    trace_mcp_tool_call,
    trace_telegram_api_call,
    add_span_attribute,
    add_span_event
)

# Trace a custom operation
async with trace_mcp_tool_call("custom_tool", {"param": "value"}):
    add_span_attribute("custom.attribute", "value")
    add_span_event("operation_started", {"step": "init"})

    # Your code here

    add_span_event("operation_completed", {"result": "success"})
```

## Performance Impact

### Tracing Overhead

- **Disabled**: ~0% overhead (mock spans)
- **Console Export**: ~1-2% overhead
- **Network Export**: ~2-5% overhead (depends on network latency)

### Memory Usage

- **Span Buffer**: ~1KB per span
- **Attribute Storage**: ~100 bytes per attribute
- **Batch Processing**: Configurable batch sizes

## Monitoring and Alerting

### Key Metrics to Monitor

```promql
# Tracing success rate
rate(opentelemetry_spans_total{status="ok"}[5m]) /
rate(opentelemetry_spans_total[5m])

# Slow spans
histogram_quantile(0.95, rate(opentelemetry_span_duration_seconds_bucket[5m]))

# Error spans
rate(opentelemetry_spans_total{status="error"}[5m])
```

### Recommended Alerts

```yaml
# High error rate
- alert: HighTracingErrorRate
  expr: rate(opentelemetry_spans_total{status="error"}[5m]) > 0.1
  labels:
    severity: warning

# Slow spans
- alert: SlowSpansDetected
  expr: histogram_quantile(0.95, rate(opentelemetry_span_duration_seconds_bucket[5m])) > 5
  labels:
    severity: info
```

## Development and Debugging

### Console Debugging

```bash
# Enable console export for development
export OTLP_EXPORTER=console
export TRACE_SAMPLING_RATE=1.0
```

### Debug Mode

```bash
# Enable detailed tracing logs
export DEBUG=true
export LOG_LEVEL=DEBUG
```

### Trace Correlation

Each request gets a unique trace ID that follows through:

1. **MCP Client** → traceparent header
2. **FastAPI** → span context extraction
3. **MCP Tool** → child span creation
4. **Telegram API** → nested span creation
5. **Response** → span completion and export

## Best Practices

### Span Naming

- Use descriptive, hierarchical names
- Include component and operation
- Follow `component.operation.suboperation` pattern

### Attribute Guidelines

- Use semantic naming conventions
- Include units in attribute names (e.g., `duration_seconds`)
- Limit attribute count per span
- Use consistent attribute names across spans

### Error Handling

- Always record exceptions with context
- Include relevant parameters in error spans
- Set appropriate span status (ERROR, OK)
- Add error events with timestamps

### Sampling Strategy

- **Development**: 100% sampling for full visibility
- **Production**: Adaptive sampling based on load
- **High-volume**: Sample errors and slow operations
- **Low-volume**: Full sampling for complete traces

## Troubleshooting

### Common Issues

#### Traces Not Appearing

**Symptoms**: No traces in your tracing backend

**Solutions**:
1. Check `OTLP_ENDPOINT` configuration
2. Verify exporter type (`grpc` vs `http`)
3. Check network connectivity to tracing backend
4. Enable console export for debugging

#### High Tracing Overhead

**Symptoms**: Performance degradation with tracing enabled

**Solutions**:
1. Reduce sampling rate
2. Use batch span processors
3. Limit attributes per span
4. Consider async span export

#### Missing Spans

**Symptoms**: Some operations not traced

**Solutions**:
1. Check if tracing is enabled globally
2. Verify span context propagation
3. Ensure all async operations are properly traced
4. Check for span context loss in error paths

## Integration Examples

### With Jaeger

```bash
# Start Jaeger
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 14268:14268 \
  jaegertracing/all-in-one:latest

# Configure application
export OTLP_EXPORTER=jaeger
export OTLP_ENDPOINT=localhost:14268

# View traces at http://localhost:16686
```

### With OpenTelemetry Collector

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

exporters:
  jaeger:
    endpoint: jaeger:14268
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [jaeger]
```

## Migration Guide

### From No Tracing

1. Add OpenTelemetry dependencies
2. Configure environment variables
3. Enable tracing in configuration
4. Deploy tracing backend (Jaeger/OTLP)
5. Verify traces are being exported

### From Basic Logging

1. Replace manual logging with span attributes
2. Add span events for key operations
3. Configure proper sampling rates
4. Set up alerting on tracing metrics
5. Integrate with existing monitoring stack

## Future Enhancements

### Planned Features

- **Trace-based alerting** on span duration anomalies
- **Distributed context propagation** across MCP boundaries
- **Custom span processors** for domain-specific logic
- **Trace sampling policies** based on business rules
- **Integration with APM tools** (DataDog, New Relic)

### Research Areas

- **AI-powered trace analysis** for anomaly detection
- **Trace-based performance profiling** for optimization
- **Cross-service trace correlation** in MCP ecosystems
- **Privacy-preserving trace sampling** for GDPR compliance
