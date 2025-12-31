import os
from pathlib import Path
from typing import Dict, Optional, List

from ..config import ALLOWED_BASE_DIR, MAX_READ_BYTES


def _resolve_path(rel_path: str) -> Path:
    """
    Resolve a user-supplied path against the allowed base directory, ensuring
    it cannot escape the allowed base (prevents directory traversal).
    """
    p = Path(rel_path)
    if not p.is_absolute():
        p = (ALLOWED_BASE_DIR / p).resolve()
    else:
        p = p.resolve()
    if not str(p).startswith(str(ALLOWED_BASE_DIR.resolve())):
        raise PermissionError("Path is outside allowed base directory")
    return p


def read(path: str, max_bytes: Optional[int] = None) -> Dict[str, object]:
    """
    Read up to max_bytes from a file at the given path.
    Returns dict with keys: ok, path, size, content, truncated or error.
    """
    max_bytes = max_bytes or MAX_READ_BYTES
    try:
        p = _resolve_path(path)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if not p.exists():
        return {"ok": False, "error": "not_found"}
    if p.is_dir():
        return {"ok": False, "error": "is_directory"}
    size = p.stat().st_size
    try:
        with p.open("rb") as f:
            content = f.read(max_bytes)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    try:
        text = content.decode("utf-8")
    except Exception:
        text = content.decode("latin-1", errors="ignore")
    return {
        "ok": True,
        "path": str(p),
        "size": size,
        "content": text,
        "truncated": size > max_bytes
    }


def write(path: str, content: str, mode: str = "overwrite") -> Dict[str, object]:
    """
    Write content to a file. Modes: overwrite or append.
    """
    try:
        p = _resolve_path(path)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        if mode == "overwrite":
            p.write_text(content, encoding="utf-8")
        elif mode == "append":
            with p.open("a", encoding="utf-8") as f:
                f.write(content)
        else:
            return {"ok": False, "error": "invalid_mode"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "path": str(p)}


def list_dir(path: str, recursive: bool = False, max_entries: int = 2000) -> Dict[str, object]:
    """
    List directory contents. Returns entries with basic metadata.
    """
    try:
        p = _resolve_path(path)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if not p.exists():
        return {"ok": False, "error": "not_found"}
    if not p.is_dir():
        return {"ok": False, "error": "not_directory"}

    base = ALLOWED_BASE_DIR.resolve()
    entries: List[Dict[str, object]] = []
    truncated = False

    def _entry_info(ep: Path) -> Dict[str, object]:
        try:
            rel_path = str(ep.resolve().relative_to(base))
        except Exception:
            rel_path = ep.name
        try:
            st = ep.stat()
        except Exception:
            st = None
        entry_type = "dir" if ep.is_dir() else "file" if ep.is_file() else "other"
        return {
            "path": str(ep),
            "rel_path": rel_path,
            "type": entry_type,
            "size": st.st_size if st else None,
            "mtime": st.st_mtime if st else None,
        }

    def _add_entry(ep: Path) -> bool:
        nonlocal truncated
        if len(entries) >= max_entries:
            truncated = True
            return False
        entries.append(_entry_info(ep))
        return True

    if recursive:
        for root, dirs, files in os.walk(p):
            for name in dirs:
                if not _add_entry(Path(root) / name):
                    break
            if truncated:
                break
            for name in files:
                if not _add_entry(Path(root) / name):
                    break
            if truncated:
                break
    else:
        for ep in p.iterdir():
            if not _add_entry(ep):
                break

    return {"ok": True, "path": str(p), "entries": entries, "truncated": truncated}


def stat(path: str) -> Dict[str, object]:
    """
    Return basic stat metadata for a path.
    """
    try:
        p = _resolve_path(path)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if not p.exists():
        return {"ok": False, "error": "not_found"}
    st = p.stat()
    entry_type = "dir" if p.is_dir() else "file" if p.is_file() else "other"
    return {
        "ok": True,
        "path": str(p),
        "type": entry_type,
        "size": st.st_size,
        "mtime": st.st_mtime,
    }
