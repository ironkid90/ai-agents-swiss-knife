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
pip install -r server/requirements.txt
```

### Running the server

Run the MCP server using Python (which internally uses `uvicorn`):

```bash
python server/mcp_server.py
```

By default, the server listens on port 8000. You can change the host/port with
the `MCP_HOST` and `MCP_PORT` environment variables.

The allowed base directory for file operations defaults to the current working
directory when the server is started. To change the sandbox root, set the
environment variable `MCP_ALLOWED_BASE` before starting the server:

```bash
export MCP_ALLOWED_BASE=/path/to/workspace
python server/mcp_server.py
```

You can also configure:

- `MCP_HOST` and `MCP_PORT` to change the bind address/port.
- `MCP_MAX_READ_BYTES` to change the default read size for `/fs/read`.
- `MCP_EXCEL_LOCK_TIMEOUT_S` to change the Excel lock timeout (seconds).

### API Endpoints

#### Health
- `GET /health` - Quick health check.
- `GET /tools/list` - Tool discovery for agents (names, routes, request schema).
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
curl -X POST http://localhost:8000/shell/exec \
  -H "Content-Type: application/json" \
  -d '{"cmd":"ls -la", "cwd":"."}'
```

The server returns JSON with `ok`, `exit_code`, `stdout`, and `stderr` fields.

Use similar JSON requests to interact with filesystem, git, and Excel endpoints.
