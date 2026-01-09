import os
from pathlib import Path

# Root directory we allow the MCP to operate on (security)
ALLOWED_BASE_DIR = Path(os.environ.get("MCP_ALLOWED_BASE", str(Path.cwd())))

# Maximum bytes to read from a file by default
MAX_READ_BYTES = int(os.environ.get("MCP_MAX_READ_BYTES", 200_000))
# Default to localhost for safety; override with MCP_HOST (e.g. 0.0.0.0) if needed.
MCP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.environ.get("MCP_PORT", 8080))
EXCEL_LOCK_TIMEOUT_S = int(os.environ.get("MCP_EXCEL_LOCK_TIMEOUT_S", 5))
