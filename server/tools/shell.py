import subprocess
from datetime import datetime
from typing import Optional, Dict


def _redact(text: str) -> str:
    """
    Very basic redaction to avoid leaking large outputs or secrets.
    Truncates long outputs and normalises newlines.
    """
    if not text:
        return text
    s = text.replace("\n", "\\n")
    return s[:20000]


def exec_cmd(cmd: str, cwd: Optional[str] = None, env: Optional[dict] = None,
             timeout_s: int = 60) -> Dict[str, object]:
    """
    Execute a shell command safely and return a structured output.
    Uses the system shell for convenience. Limits output and captures exit status.
    """
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s
        )
        return {
            "ok": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": _redact(result.stdout),
            "stderr": _redact(result.stderr),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except subprocess.TimeoutExpired as e:
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Timeout: {str(e)}"
        }
    except Exception as e:
        return {
            "ok": False,
            "exit_code": -2,
            "stdout": "",
            "stderr": f"Error: {str(e)}"
        }