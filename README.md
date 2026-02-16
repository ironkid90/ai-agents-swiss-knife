## AI agent's swiss knife

This project provides a **local MCP server** for AI agents. It exposes a
minimal yet powerful set of tools via HTTP endpoints. The tools include:

- **Shell** execution: run shell commands and get structured output.
- **Filesystem**: read and write files with sandboxed path resolution.
- **Git**: get status/diff and commit changes in a repository.
- **Excel**: inspect, read, preview changes, and commit changes to Excel workbooks
  (`.xlsx` files) using `openpyxl`. A simple file-based lock prevents concurrent edits.

### Requirements

- Python 3.10+
- Install dependencies:

```bash
pip install -e .
```

### One-command local bootstrap

Use the setup script for your shell. It creates `.venv`, installs the package, starts
the server, and validates `GET /health`.

```bash
./scripts/setup_local.sh
```

```powershell
.\scripts\setup_local.ps1
```

### Running the server

Run the MCP server using Python (which internally uses `uvicorn`):

```bash
ai-agents-swiss-knife-server
# or
python -m server.mcp_server
```

Open the GUI in your browser at `http://localhost:8080/` (redirects to Swagger UI at
`/docs`). You can also use `/redoc`.

By default, the server listens on `127.0.0.1:8080`. You can change the host/port with
the `MCP_HOST` and `MCP_PORT` environment variables.

The allowed base directory for file operations defaults to the current working
directory when the server is started. To change the sandbox root, set the
environment variable `MCP_ALLOWED_BASE` before starting the server:

```bash
export MCP_ALLOWED_BASE=/path/to/workspace
ai-agents-swiss-knife-server
# or
python -m server.mcp_server
```

You can also configure:

- `MCP_HOST` and `MCP_PORT` to change the bind address/port.
- `MCP_MAX_READ_BYTES` to change the default read size for `/fs/read`.
- `MCP_EXCEL_LOCK_TIMEOUT_S` to change the Excel lock timeout (seconds).
- `MCP_MINIMAL_MODE` (`1`/`true`) to expose only the core safe bundle in `/tools/list`.

### Tool bundles: core vs advanced

The server now supports two discovery bundles (returned by `GET /tools/list`):

- **Core bundle (minimal mode)**: high-value, read-focused, safer tools for lightweight clients.
- **Advanced bundle (default)**: full toolset, including mutation and process-control operations.

Enable core bundle mode:

```bash
export MCP_MINIMAL_MODE=1
python -m server.mcp_server
```

Disable it (default full bundle):

```bash
unset MCP_MINIMAL_MODE
python -m server.mcp_server
```

`/tools/list` now also includes each tool's `category`, `safety_level`,
`recommended_workflow_order`, and optional deprecation/replacement guidance to help
clients choose safer workflows.

### MCP client config templates

Template configs are provided under `configs/clients/`:

- `codex-cli.mcp.json`
- `gemini-cli.mcp.json`
- `generic-mcp-jsonrpc-stdio.json`

Use `--print-config` to output validated, copy/paste-ready bridge settings:

```bash
ai-agents-swiss-knife-bridge --print-config
```

### Client matrix

| Client | Transport mode | Config file location (typical) | Known limitations |
|---|---|---|---|
| Codex CLI | MCP over stdio via `ai-agents-swiss-knife-bridge` | User MCP config (copy from `configs/clients/codex-cli.mcp.json`) | Requires HTTP server to be running first. |
| Gemini CLI | MCP over stdio via `ai-agents-swiss-knife-bridge` | User MCP config (copy from `configs/clients/gemini-cli.mcp.json`) | Depends on CLI MCP support version; tool output is returned as JSON text content. |
| Generic MCP JSON-RPC client | MCP JSON-RPC over stdio via bridge | Client-specific JSON config (use `configs/clients/generic-mcp-jsonrpc-stdio.json`) | This repo currently exposes MCP through stdio bridge only (not Streamable HTTP MCP). |

### Windows service

This uses WinSW (a Windows service wrapper). The install script downloads WinSW if needed.

Run PowerShell as Administrator:

```powershell
.\scripts\install_service.ps1
```

To uninstall:

```powershell
.\scripts\uninstall_service.ps1
```

The service reads config generated from `scripts/winsw/ai-agents-swiss-knife.xml.template` and logs to `logs/server.out.log` and `logs/server.err.log`.

### Response Envelope Contract

All tool endpoints are expected to return a standardized envelope:

```json
{ "ok": true, "...tool_specific_fields": "..." }
```

or on failure:

```json
{
  "ok": false,
  "error": {
    "code": "not_found|invalid_path|permission_denied|timeout|internal_error",
    "message": "human-readable detail"
  }
}
```

Use `GET /tools/list` to discover endpoints; each tool description references this contract.

### API Endpoints

#### Health
- `GET /health` - Quick health check.
- `GET /tools/list` - Tool discovery for agents (names, routes, request schema, category, safety level, workflow order, and guidance).
- `GET /openapi.json` - OpenAPI schema for all endpoints (FastAPI default).

#### Shell
- `POST /shell/exec` - Run a shell command.
  - Parameters: `cmd` (string), optional `cwd`, `env` (object), `timeout_s` (int).
  - Returns: `ok`, `exit_code`, `stdout`, `stderr`, `timestamp`.

#### Filesystem
- `POST /fs/read` - Read a file.
  - Parameters: `path` (string), optional `max_bytes` (int).
- `POST /fs/write` - Write or append to a file.
  - Parameters: `path` (string), `content` (string), `mode` (`overwrite`/`append`).
- `POST /fs/list` - List directory contents.
  - Parameters: `path` (string), optional `recursive` (bool), `max_entries` (int).
- `POST /fs/stat` - Stat a file or directory.
  - Parameters: `path` (string).

#### Git
- `POST /git/status` - Get concise git status.
  - Parameters: optional `cwd` (string).
- `POST /git/diff` - Get diff of current changes.
- `POST /git/commit` - Stage all changes and commit with a message.
  - Parameters: `message` (string), optional `cwd` (string).

#### Search
- `POST /search/rg` - Ripgrep search with safe args.

#### Process
- `POST /process/start` - Start a long-running process.
- `POST /process/status` - Check process status.
- `POST /process/kill` - Terminate a server-started process.
- `POST /process/read` - Read captured stdout/stderr from a server-started process.
- `POST /process/list` - List server-started processes.

#### JSON
- `POST /json/patch` - Apply JSON Patch (RFC 6902) to a JSON file.

#### Zip
- `POST /zip/pack` - Create a zip archive.
- `POST /zip/unpack` - Extract a zip archive.

#### Excel
- `POST /excel/inspect` - Inspect a workbook (sheets, named ranges, tables).
- `POST /excel/read_range` - Read a range from a sheet.
- `POST /excel/preview_write` - Preview changes to a range without saving.
- `POST /excel/commit_write` - Commit changes to a range and save the workbook.
- `POST /excel/find` - Search for values across a sheet or workbook.

### Example

Run the server, then from another terminal you can call:

```bash
curl -X POST http://localhost:8080/shell/exec \
  -H "Content-Type: application/json" \
  -d '{"cmd":"ls -la", "cwd":"."}'
```

The server returns JSON with `ok`, `exit_code`, `stdout`, and `stderr` fields.

Use similar JSON requests to interact with filesystem, git, and Excel endpoints.
