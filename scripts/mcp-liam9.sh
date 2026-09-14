#!/usr/bin/env bash
# سرور MCP لیام تریدر ۹ روی stdio — بی‌وابستگی، فقط python3.
# .mcp.json ریشه این را صدا می‌زند؛ کلاینت (Claude Code / داشبورد) با
# JSON-RPC یک‌خطی حرف می‌زند. هیچ سکرتی این‌جا نیست و لازم هم نیست.
set -euo pipefail
cd "$(dirname "$0")/../claude-liam-signal/python"
exec python3 -m hamid.mcp_server --serve
