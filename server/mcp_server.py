from pathlib import Path
from typing import Any
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from server.config import MCP_HOST, MCP_PORT
from server.tools import shell, fs, git_tools, excel_mcp, search_mcp, process_mcp, json_tools, zip_tools

app = FastAPI(title="Local MCP Server for Codex")

@app.get("/", include_in_schema=False)
def root():
    """Landing page: send humans to the interactive API docs (Swagger UI)."""
    return RedirectResponse(url="/docs")

@app.get("/health")
def health():
    return {"ok": True}


class ShellExecRequest(BaseModel):
    cmd: str
    cwd: str | None = None
    env: dict | None = None
    timeout_s: int = 60


@app.post("/shell/exec")
def shell_exec(req: ShellExecRequest):
    """Execute a shell command and return structured output."""
    try:
        return shell.exec_cmd(req.cmd, cwd=req.cwd, env=req.env, timeout_s=req.timeout_s)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class FSReadRequest(BaseModel):
    path: str
    max_bytes: int | None = None


@app.post("/fs/read")
def fs_read(req: FSReadRequest):
    """Read a file and return its content."""
    return fs.read(req.path, max_bytes=req.max_bytes)


class FSWriteRequest(BaseModel):
    path: str
    content: str
    mode: str = "overwrite"


@app.post("/fs/write")
def fs_write(req: FSWriteRequest):
    """Write content to a file."""
    return fs.write(req.path, req.content, req.mode)


class FSListRequest(BaseModel):
    path: str
    recursive: bool = False
    max_entries: int | None = None


@app.post("/fs/list")
def fs_list(req: FSListRequest):
    max_entries = req.max_entries if req.max_entries is not None else 2000
    return fs.list_dir(req.path, recursive=req.recursive, max_entries=max_entries)


class FSStatRequest(BaseModel):
    path: str


@app.post("/fs/stat")
def fs_stat(req: FSStatRequest):
    return fs.stat(req.path)


class GitRequest(BaseModel):
    cwd: str | None = None


@app.post("/git/status")
def git_status(req: GitRequest):
    return git_tools.git_status(cwd=req.cwd)


@app.post("/git/diff")
def git_diff(req: GitRequest):
    return git_tools.git_diff(cwd=req.cwd)


class GitCommitRequest(BaseModel):
    message: str
    cwd: str | None = None


@app.post("/git/commit")
def git_commit(req: GitCommitRequest):
    return git_tools.git_commit(req.message, cwd=req.cwd)


class SearchRequest(BaseModel):
    pattern: str
    path: str | None = None
    glob: list | str | None = None
    case_sensitive: bool | None = None
    fixed_strings: bool = False
    max_results: int = 200
    timeout_s: int = 30


@app.post("/search/rg")
def search_rg(req: SearchRequest):
    return search_mcp.rg_search(
        req.pattern,
        path=req.path or ".",
        glob=req.glob,
        case_sensitive=req.case_sensitive,
        fixed_strings=req.fixed_strings,
        max_results=req.max_results,
        timeout_s=req.timeout_s,
    )


class ProcessStartRequest(BaseModel):
    cmd: str
    cwd: str | None = None
    env: dict | None = None
    capture_output: bool = True


@app.post("/process/start")
def process_start(req: ProcessStartRequest):
    return process_mcp.start(req.cmd, cwd=req.cwd, env=req.env, capture_output=req.capture_output)


class ProcessStatusRequest(BaseModel):
    pid: int


@app.post("/process/status")
def process_status(req: ProcessStatusRequest):
    return process_mcp.status(req.pid)


class ProcessKillRequest(BaseModel):
    pid: int
    force: bool = False
    timeout_s: int = 5


@app.post("/process/kill")
def process_kill(req: ProcessKillRequest):
    return process_mcp.kill(req.pid, force=req.force, timeout_s=req.timeout_s)


class ProcessReadRequest(BaseModel):
    pid: int
    stream: str = "stdout"
    max_bytes: int = 20000
    tail: bool = True


@app.post("/process/read")
def process_read(req: ProcessReadRequest):
    return process_mcp.read(req.pid, stream=req.stream, max_bytes=req.max_bytes, tail=req.tail)


@app.post("/process/list")
def process_list():
    return process_mcp.list_processes()


class JsonPatchRequest(BaseModel):
    path: str
    patch: list
    create_if_missing: bool = False


@app.post("/json/patch")
def json_patch(req: JsonPatchRequest):
    return json_tools.patch_file(req.path, req.patch, create_if_missing=req.create_if_missing)


class ZipPackRequest(BaseModel):
    paths: list
    dest_path: str
    overwrite: bool = False


@app.post("/zip/pack")
def zip_pack(req: ZipPackRequest):
    return zip_tools.pack(req.paths, req.dest_path, overwrite=req.overwrite)


class ZipUnpackRequest(BaseModel):
    zip_path: str
    dest_dir: str
    overwrite: bool = False


@app.post("/zip/unpack")
def zip_unpack(req: ZipUnpackRequest):
    return zip_tools.unpack(req.zip_path, req.dest_dir, overwrite=req.overwrite)


class ExcelInspectRequest(BaseModel):
    workbook_path: str


@app.post("/excel/inspect")
def excel_inspect(req: ExcelInspectRequest):
    return excel_mcp.inspect(req.workbook_path)


class ExcelReadRequest(BaseModel):
    workbook_path: str
    sheet: str
    a1_range: str
    top_n: int | None = None


@app.post("/excel/read_range")
def excel_read_range(req: ExcelReadRequest):
    return excel_mcp.read_range(req.workbook_path, req.sheet, req.a1_range, req.top_n)


class ExcelPreviewRequest(BaseModel):
    workbook_path: str
    sheet: str
    a1_range: str
    values: list


@app.post("/excel/preview_write")
def excel_preview(req: ExcelPreviewRequest):
    return excel_mcp.preview_write(req.workbook_path, req.sheet, req.a1_range, req.values)


@app.post("/excel/commit_write")
def excel_commit(req: ExcelPreviewRequest):
    return excel_mcp.commit_write(req.workbook_path, req.sheet, req.a1_range, req.values)


class ExcelFindRequest(BaseModel):
    workbook_path: str
    query: Any
    sheet: str | None = None
    a1_range: str | None = None
    match_case: bool = False
    exact: bool = False
    limit: int = 100


@app.post("/excel/find")
def excel_find(req: ExcelFindRequest):
    return excel_mcp.find(
        req.workbook_path,
        req.query,
        sheet=req.sheet,
        a1_range=req.a1_range,
        match_case=req.match_case,
        exact=req.exact,
        limit=req.limit,
    )


def _model_schema(model: type[BaseModel]) -> dict:
    if hasattr(model, "model_json_schema"):
        return model.model_json_schema()
    return model.schema()


@app.get("/tools/list")
def tools_list():
    tools = [
        {"name": "health", "method": "GET", "path": "/health", "description": "Health check"},
        {"name": "shell.exec", "method": "POST", "path": "/shell/exec", "description": "Execute a shell command", "request_schema": _model_schema(ShellExecRequest)},
        {"name": "fs.read", "method": "POST", "path": "/fs/read", "description": "Read a file", "request_schema": _model_schema(FSReadRequest)},
        {"name": "fs.write", "method": "POST", "path": "/fs/write", "description": "Write a file", "request_schema": _model_schema(FSWriteRequest)},
        {"name": "fs.list", "method": "POST", "path": "/fs/list", "description": "List directory contents", "request_schema": _model_schema(FSListRequest)},
        {"name": "fs.stat", "method": "POST", "path": "/fs/stat", "description": "Stat a file or directory", "request_schema": _model_schema(FSStatRequest)},
        {"name": "git.status", "method": "POST", "path": "/git/status", "description": "Git status", "request_schema": _model_schema(GitRequest)},
        {"name": "git.diff", "method": "POST", "path": "/git/diff", "description": "Git diff", "request_schema": _model_schema(GitRequest)},
        {"name": "git.commit", "method": "POST", "path": "/git/commit", "description": "Git commit", "request_schema": _model_schema(GitCommitRequest)},
        {"name": "search.rg", "method": "POST", "path": "/search/rg", "description": "Ripgrep search", "request_schema": _model_schema(SearchRequest)},
        {"name": "process.start", "method": "POST", "path": "/process/start", "description": "Start a process", "request_schema": _model_schema(ProcessStartRequest)},
        {"name": "process.status", "method": "POST", "path": "/process/status", "description": "Process status", "request_schema": _model_schema(ProcessStatusRequest)},
        {"name": "process.kill", "method": "POST", "path": "/process/kill", "description": "Kill a process started by the server", "request_schema": _model_schema(ProcessKillRequest)},
        {"name": "process.read", "method": "POST", "path": "/process/read", "description": "Read process output", "request_schema": _model_schema(ProcessReadRequest)},
        {"name": "process.list", "method": "POST", "path": "/process/list", "description": "List server-started processes"},
        {"name": "json.patch", "method": "POST", "path": "/json/patch", "description": "Apply JSON patch to file", "request_schema": _model_schema(JsonPatchRequest)},
        {"name": "zip.pack", "method": "POST", "path": "/zip/pack", "description": "Create zip archive", "request_schema": _model_schema(ZipPackRequest)},
        {"name": "zip.unpack", "method": "POST", "path": "/zip/unpack", "description": "Extract zip archive", "request_schema": _model_schema(ZipUnpackRequest)},
        {"name": "excel.inspect", "method": "POST", "path": "/excel/inspect", "description": "Inspect workbook", "request_schema": _model_schema(ExcelInspectRequest)},
        {"name": "excel.read_range", "method": "POST", "path": "/excel/read_range", "description": "Read range", "request_schema": _model_schema(ExcelReadRequest)},
        {"name": "excel.preview_write", "method": "POST", "path": "/excel/preview_write", "description": "Preview write", "request_schema": _model_schema(ExcelPreviewRequest)},
        {"name": "excel.commit_write", "method": "POST", "path": "/excel/commit_write", "description": "Commit write", "request_schema": _model_schema(ExcelPreviewRequest)},
        {"name": "excel.find", "method": "POST", "path": "/excel/find", "description": "Find values", "request_schema": _model_schema(ExcelFindRequest)},
    ]
    return {"ok": True, "tools": tools}


def run() -> None:
    import uvicorn

    uvicorn.run(app, host=MCP_HOST, port=MCP_PORT)


if __name__ == "__main__":
    run()
