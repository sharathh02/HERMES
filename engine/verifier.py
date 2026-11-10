"""
HERMES Verifier Module
Extracts Python code snippets from Markdown documentation and executes them
in a bounded, isolated subprocess to verify executable correctness.
"""

import re
import os
import sys
import subprocess
import time
import tempfile
from typing import List, Dict, Any, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_BIN = os.path.join(os.path.dirname(PROJECT_ROOT), "python", "python.exe")
if not os.path.exists(PYTHON_BIN):
    PYTHON_BIN = sys.executable


def extract_python_snippets(markdown_content: str) -> List[Dict[str, Any]]:
    """
    Extract all ```python ... ``` blocks with their line offsets and identifiers.
    """
    pattern = re.compile(r"```python\s*\n(.*?)\n```", re.DOTALL)
    snippets = []
    lines = markdown_content.splitlines()

    for match_index, match in enumerate(pattern.finditer(markdown_content)):
        code = match.group(1).strip()
        # Find start line
        start_char = match.start()
        line_num = markdown_content[:start_char].count("\n") + 1

        snippet_id = f"snippet-{match_index + 1}-L{line_num}"
        snippets.append({
            "id": snippet_id,
            "index": match_index + 1,
            "start_line": line_num,
            "code": code
        })

    return snippets


def execute_snippet(snippet_code: str, timeout_seconds: float = 5.0) -> Dict[str, Any]:
    """
    Execute a code snippet in an isolated Python subprocess with timeout,
    restricted environment, and standard output/error capture.
    """
    start_time = time.time()
    
    # Prepare execution environment
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    # Write snippet to a temporary script file
    temp_dir = tempfile.gettempdir()
    script_path = os.path.join(temp_dir, f"hermes_snippet_{int(time.time()*1000)}.py")

    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(snippet_code)

        proc = subprocess.run(
            [PYTHON_BIN, script_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env
        )
        duration_ms = round((time.time() - start_time) * 1000, 2)

        if proc.returncode == 0:
            return {
                "status": "Passed",
                "returncode": 0,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "execution_time_ms": duration_ms,
                "error": None
            }
        else:
            return {
                "status": "Failed",
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "execution_time_ms": duration_ms,
                "error": proc.stderr or proc.stdout
            }

    except subprocess.TimeoutExpired:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "Failed",
            "returncode": -1,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout_seconds}s limit exceeded.",
            "execution_time_ms": duration_ms,
            "error": "TimeoutExpired"
        }
    except Exception as e:
        duration_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "Failed",
            "returncode": -1,
            "stdout": "",
            "stderr": f"Subprocess invocation error: {str(e)}",
            "execution_time_ms": duration_ms,
            "error": str(e)
        }
    finally:
        if os.path.exists(script_path):
            try:
                os.remove(script_path)
            except Exception:
                pass


def verify_markdown_document(markdown_content: str, timeout_seconds: float = 5.0) -> List[Dict[str, Any]]:
    """
    Extract and verify all code snippets in a documentation document.
    """
    snippets = extract_python_snippets(markdown_content)
    results = []

    for snippet in snippets:
        exec_result = execute_snippet(snippet["code"], timeout_seconds=timeout_seconds)
        results.append({
            "snippet_id": snippet["id"],
            "line": snippet["start_line"],
            "code": snippet["code"],
            "status": exec_result["status"],
            "stdout": exec_result["stdout"],
            "stderr": exec_result["stderr"],
            "execution_time_ms": exec_result["execution_time_ms"],
            "error": exec_result["error"]
        })

    return results
