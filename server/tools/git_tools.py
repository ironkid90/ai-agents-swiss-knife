from typing import Dict, Optional

from .shell import exec_cmd


def git_status(cwd: Optional[str] = None) -> Dict[str, object]:
    """
    Return git status in a concise form. Includes branch info, staged/unstaged/unsttracked files.
    """
    return exec_cmd("git status --porcelain --branch --untracked-files=all", cwd=cwd)


def git_diff(cwd: Optional[str] = None) -> Dict[str, object]:
    """
    Return the current diff (staged and unstaged) without color codes.
    """
    return exec_cmd("git --no-pager diff --no-color", cwd=cwd)


def git_commit(message: str, cwd: Optional[str] = None) -> Dict[str, object]:
    """
    Stage all changes and commit with the given message.
    """
    add_result = exec_cmd("git add -A", cwd=cwd)
    if not add_result.get("ok"):
        return add_result
    # Use format to avoid quoting issues
    return exec_cmd('git commit -m "{}"'.format(message), cwd=cwd)