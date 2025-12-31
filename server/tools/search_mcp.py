import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional, List, Any

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


def rg_search(
    pattern: str,
    path: str = ".",
    glob: Optional[List[str] | str] = None,
    case_sensitive: Optional[bool] = None,
    fixed_strings: bool = False,
    max_results: int = 200,
    timeout_s: int = 30,
) -> Dict[str, Any]:
    """
    Run ripgrep with safe args and return structured matches.
    """
    if not pattern:
        return {"ok": False, "error": "empty_pattern"}
    rg_path = shutil.which("rg")
    if not rg_path:
        return {"ok": False, "error": "rg_not_found"}

    try:
        target = _resolve_path(path)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    args = [rg_path, "--json"]
    if fixed_strings:
        args.append("-F")
    if case_sensitive is True:
        args.append("-s")
    elif case_sensitive is False:
        args.append("-i")
    if glob:
        if isinstance(glob, list):
            for g in glob:
                args.extend(["--glob", g])
        else:
            args.extend(["--glob", glob])
    args.extend([pattern, str(target)])

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    if result.returncode not in (0, 1):
        return {
            "ok": False,
            "error": "rg_failed",
            "exit_code": result.returncode,
            "stderr": result.stderr.strip(),
        }

    matches: List[Dict[str, Any]] = []
    truncated = False
    for line in result.stdout.splitlines():
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if payload.get("type") != "match":
            continue
        data = payload.get("data", {})
        path_text = data.get("path", {}).get("text")
        line_number = data.get("line_number")
        line_text = data.get("lines", {}).get("text", "").rstrip("\n")
        submatches = []
        for sm in data.get("submatches", []):
            submatches.append({"start": sm.get("start"), "end": sm.get("end")})
        matches.append(
            {
                "path": path_text,
                "line_number": line_number,
                "line": line_text,
                "submatches": submatches,
            }
        )
        if len(matches) >= max_results:
            truncated = True
            break

    return {
        "ok": True,
        "matches": matches,
        "truncated": truncated,
        "exit_code": result.returncode,
    }
