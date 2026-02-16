import argparse
import json
import os
import sys
from typing import Any, Dict, Optional
from urllib import error, parse, request

DEFAULT_BASE_URL = "http://localhost:8080"
SERVER_NAME = "ai-agents-swiss-knife"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


def _validated_base_url(raw_url: Optional[str]) -> str:
    candidate = (raw_url or os.environ.get("MCP_BASE_URL") or DEFAULT_BASE_URL).strip()
    parsed = parse.urlsplit(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("MCP_BASE_URL must start with http:// or https://")
    if not parsed.netloc:
        raise ValueError("MCP_BASE_URL must include a host (and optional port)")
    path = parsed.path.rstrip("/")
    normalized = parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
    return normalized


def _http_json(base_url: str, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{base_url}{path}"
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


def _get_tools_cache(base_url: str) -> Dict[str, Dict[str, Any]]:
    resp = _http_json(base_url, "GET", "/tools/list")
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
    base_url: str,
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
        result = _http_json(base_url, "GET", path)
    else:
        result = _http_json(base_url, "POST", path, payload)
    return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=True)}]}


def _handle_request(base_url: str, req: Dict[str, Any], tools_cache: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
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
        result = _tool_call(base_url, tools_cache, name, arguments)
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "shutdown":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    return None


def _print_config(base_url: str) -> int:
    health = _http_json(base_url, "GET", "/health")
    config = {
        "server": SERVER_NAME,
        "version": SERVER_VERSION,
        "protocolVersion": PROTOCOL_VERSION,
        "baseUrl": base_url,
        "healthUrl": f"{base_url}/health",
        "toolsUrl": f"{base_url}/tools/list",
        "health": health,
        "bridgeCommand": {
            "command": "ai-agents-swiss-knife-bridge",
            "env": {"MCP_BASE_URL": base_url},
        },
    }
    print(json.dumps(config, indent=2))
    return 0


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MCP stdio bridge for ai-agents-swiss-knife")
    parser.add_argument("--base-url", help="Override MCP_BASE_URL for this run")
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Print validated bridge connection settings as JSON and exit",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args()
    try:
        base_url = _validated_base_url(args.base_url)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)

    if args.print_config:
        raise SystemExit(_print_config(base_url))

    tools_cache = _get_tools_cache(base_url)
    while True:
        req = _read_message()
        if req is None:
            break
        if req.get("method") == "shutdown":
            resp = _handle_request(base_url, req, tools_cache)
            if resp:
                _send_message(resp)
            break
        resp = _handle_request(base_url, req, tools_cache)
        if resp:
            _send_message(resp)


if __name__ == "__main__":
    main()
