import os
import zipfile
from pathlib import Path
from typing import Dict, List

from ..config import ALLOWED_BASE_DIR


def _resolve_path(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = (ALLOWED_BASE_DIR / p).resolve()
    else:
        p = p.resolve()
    if not str(p).startswith(str(ALLOWED_BASE_DIR.resolve())):
        raise PermissionError("Path is outside allowed base directory")
    return p


def pack(paths: List[str], dest_path: str, overwrite: bool = False) -> Dict[str, object]:
    """
    Pack files/directories into a zip archive.
    """
    if not paths:
        return {"ok": False, "error": "empty_paths"}
    try:
        dest = _resolve_path(dest_path)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if dest.exists() and not overwrite:
        return {"ok": False, "error": "dest_exists"}
    dest.parent.mkdir(parents=True, exist_ok=True)

    base = ALLOWED_BASE_DIR.resolve()
    count = 0
    try:
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for item in paths:
                try:
                    p = _resolve_path(item)
                except Exception as e:
                    return {"ok": False, "error": str(e)}
                if p.is_file():
                    arcname = str(p.resolve().relative_to(base))
                    zf.write(p, arcname)
                    count += 1
                elif p.is_dir():
                    for root, _, files in os.walk(p):
                        for name in files:
                            fp = Path(root) / name
                            arcname = str(fp.resolve().relative_to(base))
                            zf.write(fp, arcname)
                            count += 1
                else:
                    return {"ok": False, "error": "unsupported_path"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    return {"ok": True, "path": str(dest), "count": count}


def unpack(zip_path: str, dest_dir: str, overwrite: bool = False) -> Dict[str, object]:
    """
    Unpack a zip archive to a destination directory.
    """
    try:
        src = _resolve_path(zip_path)
        dest = _resolve_path(dest_dir)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if not src.exists():
        return {"ok": False, "error": "not_found"}
    dest.mkdir(parents=True, exist_ok=True)

    count = 0
    try:
        with zipfile.ZipFile(src, "r") as zf:
            for member in zf.infolist():
                target = (dest / member.filename).resolve()
                if not str(target).startswith(str(dest.resolve())):
                    return {"ok": False, "error": "invalid_member_path"}
                if target.exists() and not overwrite:
                    return {"ok": False, "error": "dest_exists"}
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member, "r") as src_f, target.open("wb") as dst_f:
                    dst_f.write(src_f.read())
                count += 1
    except Exception as e:
        return {"ok": False, "error": str(e)}

    return {"ok": True, "path": str(dest), "count": count}
