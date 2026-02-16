import json
import os
import sys
from typing import Any, Dict, Optional
from urllib import error, request

from server.mcp_transport import MCPTransport

BASE_URL = os.environ.get("MCP_BASE_URL", "http://localhost:8000").rstrip("/")
SERVER_NAME = "ai-agents-swiss-knife"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"
TOOLS_CACHE_TTL_S = float(os.environ.get("MCP_TOOLS_CACHE_TTL_S", "5"))


def _http_json(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return {"ok": False, "error": "invalid_backend_response", "raw": raw}
    except error.HTTPError as e:
        status = getattr(e, "code", None)
        try:
            raw = e.read().decode("utf-8")
            parsed = json.loads(raw)
            return {"ok": False, "error": "http_error", "status": status, "response": parsed}
        except Exception:
            return {"ok": False, "error": "http_error", "status": status, "response": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _read_message() -> Optional[Dict[str, Any]]:
    stdin = sys.stdin.buffer
    headers = {}
    while True:
        line = stdin.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        try:
            key, value = line.decode("utf-8").split(":", 1)
            headers[key.strip().lower()] = value.strip()
        except Exception:
            continue
    content_length = int(headers.get("content-length", "0"))
    if content_length <= 0:
        return None
    body = stdin.read(content_length)
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return None


def _send_message(obj: Dict[str, Any]) -> None:
    data = json.dumps(obj, ensure_ascii=True).encode("utf-8")
    header = f"Content-Length: {len(data)}\r\n\r\n".encode("utf-8")
    stdout = sys.stdout.buffer
    stdout.write(header)
    stdout.write(data)
    stdout.flush()


def _fetch_tools() -> Dict[str, Dict[str, Any]]:
    resp = _http_json("GET", "/tools/list")
    tools: Dict[str, Dict[str, Any]] = {}
    if resp.get("ok"):
        for tool in resp.get("tools", []):
            tools[tool["name"]] = tool
    return tools


def _call_tool(tool: Dict[str, Any], arguments: Dict[str, Any]) -> Dict[str, Any]:
    method = tool.get("method", "POST")
    path = tool.get("path", "")
    if method == "GET":
        return _http_json("GET", path)
    return _http_json("POST", path, arguments)


def main() -> None:
    transport = MCPTransport(
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        protocol_version=PROTOCOL_VERSION,
        tools_provider=_fetch_tools,
        tools_caller=_call_tool,
        tools_cache_ttl_s=TOOLS_CACHE_TTL_S,
        enable_resources=False,
        enable_prompts=False,
    )

    while True:
        req = _read_message()
        if req is None:
            break
        resp = transport.handle_request(req)
        if resp:
            _send_message(resp)
        if req.get("method") == "shutdown":
            break


if __name__ == "__main__":
    main()
