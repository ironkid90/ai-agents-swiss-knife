import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, Any, List

from ..config import ALLOWED_BASE_DIR

_PROC_LOCK = threading.Lock()
_PROCS: Dict[int, Dict[str, Any]] = {}
_PROC_DIR_NAME = ".mcp/process"


def _resolve_cwd(cwd: Optional[str]) -> Optional[str]:
    if cwd is None:
        return None
    p = Path(cwd)
    if not p.is_absolute():
        p = (ALLOWED_BASE_DIR / p).resolve()
    else:
        p = p.resolve()
    if not str(p).startswith(str(ALLOWED_BASE_DIR.resolve())):
        raise PermissionError("Path is outside allowed base directory")
    return str(p)


def _ensure_proc_dir() -> Path:
    base = ALLOWED_BASE_DIR.resolve()
    proc_dir = base / _PROC_DIR_NAME
    proc_dir.mkdir(parents=True, exist_ok=True)
    return proc_dir


def _close_handles(entry: Dict[str, Any]) -> None:
    for key in ("stdout_handle", "stderr_handle"):
        handle = entry.get(key)
        if handle and not handle.closed:
            try:
                handle.close()
            except Exception:
                pass


def start(
    cmd: str,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    capture_output: bool = True,
) -> Dict[str, object]:
    """
    Start a long-running process and return its PID.
    """
    if not cmd:
        return {"ok": False, "error": "empty_cmd"}
    try:
        resolved_cwd = _resolve_cwd(cwd)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    stdout_handle = None
    stderr_handle = None
    stdout_path = None
    stderr_path = None
    try:
        if capture_output:
            proc_dir = _ensure_proc_dir()
            token = uuid.uuid4().hex
            stdout_path = proc_dir / f"{token}.stdout.log"
            stderr_path = proc_dir / f"{token}.stderr.log"
            stdout_handle = stdout_path.open("wb")
            stderr_handle = stderr_path.open("wb")
            stdout_stream = stdout_handle
            stderr_stream = stderr_handle
        else:
            stdout_stream = subprocess.DEVNULL
            stderr_stream = subprocess.DEVNULL
        proc = subprocess.Popen(
            cmd,
            shell=True,
            cwd=resolved_cwd,
            env=env,
            stdout=stdout_stream,
            stderr=stderr_stream,
        )
    except Exception as e:
        if stdout_handle:
            stdout_handle.close()
        if stderr_handle:
            stderr_handle.close()
        return {"ok": False, "error": str(e)}
    with _PROC_LOCK:
        _PROCS[proc.pid] = {
            "proc": proc,
            "cmd": cmd,
            "cwd": resolved_cwd,
            "start_time": time.time(),
            "stdout_path": str(stdout_path) if stdout_path else None,
            "stderr_path": str(stderr_path) if stderr_path else None,
            "stdout_handle": stdout_handle,
            "stderr_handle": stderr_handle,
            "capture_output": capture_output,
        }
    return {
        "ok": True,
        "pid": proc.pid,
        "cwd": resolved_cwd,
        "stdout_path": str(stdout_path) if stdout_path else None,
        "stderr_path": str(stderr_path) if stderr_path else None,
    }


def status(pid: int) -> Dict[str, object]:
    """
    Return process status for a PID started by this server.
    """
    with _PROC_LOCK:
        entry = _PROCS.get(pid)
    if not entry:
        return {"ok": False, "error": "not_found"}
    proc = entry["proc"]
    running = proc.poll() is None
    if not running:
        _close_handles(entry)
    return {
        "ok": True,
        "pid": pid,
        "running": running,
        "returncode": proc.returncode,
        "cmd": entry.get("cmd"),
        "cwd": entry.get("cwd"),
        "start_time": entry.get("start_time"),
        "stdout_path": entry.get("stdout_path"),
        "stderr_path": entry.get("stderr_path"),
    }


def kill(pid: int, force: bool = False, timeout_s: int = 5) -> Dict[str, object]:
    """
    Terminate a process started by this server.
    """
    with _PROC_LOCK:
        entry = _PROCS.get(pid)
    if not entry:
        return {"ok": False, "error": "not_found"}
    proc = entry["proc"]
    if proc.poll() is not None:
        _close_handles(entry)
        return {"ok": True, "status": "exited", "returncode": proc.returncode}
    try:
        proc.terminate()
        proc.wait(timeout=timeout_s)
    except Exception:
        if force:
            try:
                proc.kill()
                proc.wait(timeout=timeout_s)
            except Exception as e:
                return {"ok": False, "error": str(e)}
        else:
            return {"ok": False, "error": "timeout"}
    _close_handles(entry)
    return {"ok": True, "status": "terminated", "returncode": proc.returncode}


def read(pid: int, stream: str = "stdout", max_bytes: int = 20000, tail: bool = True) -> Dict[str, object]:
    """
    Read captured output for a process started by this server.
    """
    with _PROC_LOCK:
        entry = _PROCS.get(pid)
    if not entry:
        return {"ok": False, "error": "not_found"}
    if not entry.get("capture_output"):
        return {"ok": False, "error": "no_output"}
    path = entry.get("stdout_path") if stream == "stdout" else entry.get("stderr_path")
    if not path:
        return {"ok": False, "error": "no_output"}
    p = Path(path)
    if not p.exists():
        return {"ok": False, "error": "not_found"}
    try:
        size = p.stat().st_size
        with p.open("rb") as f:
            if tail and size > max_bytes:
                f.seek(size - max_bytes)
            data = f.read(max_bytes)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    try:
        text = data.decode("utf-8")
    except Exception:
        text = data.decode("latin-1", errors="ignore")
    return {
        "ok": True,
        "pid": pid,
        "stream": stream,
        "size": size,
        "content": text,
        "truncated": size > max_bytes if tail else len(data) >= max_bytes,
    }


def list_processes() -> Dict[str, object]:
    """
    List processes started by this server.
    """
    items: List[Dict[str, Any]] = []
    with _PROC_LOCK:
        pids = list(_PROCS.keys())
    for pid in pids:
        info = status(pid)
        if info.get("ok"):
            items.append(info)
    return {"ok": True, "processes": items}
