import json
import os
import sys
from typing import Any, Dict, Optional
from urllib import request, error

BASE_URL = os.environ.get("MCP_BASE_URL", "http://localhost:8000").rstrip("/")
SERVER_NAME = "ai-agents-swiss-knife"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


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
            return json.loads(raw)
    except error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8")
            return {"ok": False, "error": raw}
        except Exception:
            return {"ok": False, "error": str(e)}
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


def _get_tools_cache() -> Dict[str, Dict[str, Any]]:
    resp = _http_json("GET", "/tools/list")
    tools = {}
    if resp.get("ok"):
        for tool in resp.get("tools", []):
            tools[tool["name"]] = tool
    return tools


def _tools_list(tools_cache: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    tools = []
    for tool in tools_cache.values():
        if tool.get("path") in ("/health", "/tools/list", "/openapi.json"):
            continue
        tools.append(
            {
                "name": tool.get("name"),
                "description": tool.get("description") or "",
                "inputSchema": tool.get("request_schema") or {"type": "object"},
            }
        )
    return {"tools": tools}


def _tool_call(
    tools_cache: Dict[str, Dict[str, Any]],
    name: str,
    arguments: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    tool = tools_cache.get(name)
    if not tool:
        return {"content": [{"type": "text", "text": json.dumps({"ok": False, "error": "tool_not_found"})}]}
    method = tool.get("method", "POST")
    path = tool.get("path", "")
    payload = arguments or {}
    if method == "GET":
        result = _http_json("GET", path)
    else:
        result = _http_json("POST", path, payload)
    return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=True)}]}


def _handle_request(req: Dict[str, Any], tools_cache: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    if method == "tools/list":
        result = _tools_list(tools_cache)
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments")
        result = _tool_call(tools_cache, name, arguments)
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "shutdown":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    return None


def main() -> None:
    tools_cache = _get_tools_cache()
    while True:
        req = _read_message()
        if req is None:
            break
        if req.get("method") == "shutdown":
            resp = _handle_request(req, tools_cache)
            if resp:
                _send_message(resp)
            break
        resp = _handle_request(req, tools_cache)
        if resp:
            _send_message(resp)


if __name__ == "__main__":
    main()
