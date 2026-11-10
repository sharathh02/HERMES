"""
HERMES Bounded Self-Correction Loop Module
When an executable code snippet fails verification, this module provides
a bounded feedback loop:
1. Parse error traceback and failure category
2. Generate candidate correction using AST knowledge or LLM
3. Retest in isolated environment
4. Record iteration history and update documentation if verified
"""

import re
import requests
from typing import Dict, Any, List, Optional
from .verifier import execute_snippet


def heuristic_fix_snippet(code: str, stderr: str) -> Optional[str]:
    """
    Apply rule-based AST and exception pattern repairs for common snippet errors.
    """
    fixed = code

    # Pattern 1: Missing import for common modules
    if "NameError: name 'time' is not defined" in stderr:
        fixed = "import time\n" + fixed
        return fixed
    if "NameError: name 'json' is not defined" in stderr:
        fixed = "import json\n" + fixed
        return fixed
    if "NameError: name 'os' is not defined" in stderr:
        fixed = "import os\n" + fixed
        return fixed

    # Pattern 2: Missing required schema fields in sample data_pipeline
    if "ValueError: Invalid record structure" in stderr:
        # Check if record is missing timestamp or payload
        fixed = re.sub(
            r'\{(?:"id":\s*[^,}]+)\}',
            '{"id": "REC-01", "timestamp": 1700000000, "payload": {"status": "active"}}',
            fixed
        )
        if fixed != code:
            return fixed

    # Pattern 3: TypeError unexpected keyword argument
    match = re.search(r"TypeError: .* got an unexpected keyword argument '(\w+)'", stderr)
    if match:
        bad_arg = match.group(1)
        # Remove bad_arg=...
        fixed = re.sub(rf",?\s*{bad_arg}\s*=\s*[^,)\n]+", "", fixed)
        if fixed != code:
            return fixed

    # Pattern 4: Module path missing 'sample_files.' prefix
    if "ModuleNotFoundError: No module named 'data_pipeline'" in stderr:
        fixed = fixed.replace("import data_pipeline", "from sample_files import data_pipeline")
        fixed = fixed.replace("from data_pipeline import", "from sample_files.data_pipeline import")
        return fixed

    if "ModuleNotFoundError: No module named 'auth_service'" in stderr:
        fixed = fixed.replace("import auth_service", "from sample_files import auth_service")
        fixed = fixed.replace("from auth_service import", "from sample_files.auth_service import")
        return fixed

    if "ModuleNotFoundError: No module named 'cache_client'" in stderr:
        fixed = fixed.replace("import cache_client", "from sample_files import cache_client")
        fixed = fixed.replace("from cache_client import", "from sample_files.cache_client import")
        return fixed

    return None


def llm_fix_snippet(code: str, stderr: str, api_key: str, provider: str = "gemini") -> Optional[str]:
    """
    Use LLM API to repair the broken snippet based on error traceback.
    """
    prompt = f"""You are HERMES Code Repair Engine.
The following Python code snippet failed execution:

```python
{code}
```

Error / Traceback:
```
{stderr}
```

Fix the code so that it executes cleanly with return code 0.
Rules:
1. Return ONLY the executable Python code inside a ```python ... ``` block.
2. Maintain self-contained execution with assertions or print output.
3. Do not add conversational explanations.
"""
    try:
        if provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                m = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
                return m.group(1).strip() if m else text.strip()
        elif provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
                timeout=15
            )
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"]
                m = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
                return m.group(1).strip() if m else text.strip()
    except Exception:
        return None
    return None


def run_bounded_correction_loop(
    original_code: str,
    initial_stderr: str,
    max_attempts: int = 2,
    api_key: Optional[str] = None,
    provider: str = "offline_engine"
) -> Dict[str, Any]:
    """
    Execute up to `max_attempts` correction cycles.
    Returns audit history of attempts and final status.
    """
    history: List[Dict[str, Any]] = []
    current_code = original_code
    current_stderr = initial_stderr

    for attempt in range(1, max_attempts + 1):
        candidate_code = None
        method = "deterministic_heuristics"

        if api_key and provider in ("gemini", "openai"):
            candidate_code = llm_fix_snippet(current_code, current_stderr, api_key, provider)
            if candidate_code:
                method = f"llm_{provider}"

        if not candidate_code:
            candidate_code = heuristic_fix_snippet(current_code, current_stderr)
            method = "deterministic_heuristics"

        if not candidate_code or candidate_code == current_code:
            history.append({
                "attempt": attempt,
                "action": "Correction generation stalled or produced identical snippet",
                "method": method,
                "status": "Failed"
            })
            break

        # Retest candidate code
        test_result = execute_snippet(candidate_code, timeout_seconds=5.0)

        history.append({
            "attempt": attempt,
            "method": method,
            "candidate_code": candidate_code,
            "status": test_result["status"],
            "stdout": test_result["stdout"],
            "stderr": test_result["stderr"],
            "duration_ms": test_result["execution_time_ms"]
        })

        if test_result["status"] == "Passed":
            return {
                "success": True,
                "attempts_taken": attempt,
                "history": history,
                "original_code": original_code,
                "final_code": candidate_code,
                "stdout": test_result["stdout"],
                "final_result": "Passed"
            }

        # Update for next iteration
        current_code = candidate_code
        current_stderr = test_result["stderr"]

    return {
        "success": False,
        "attempts_taken": len(history),
        "history": history,
        "original_code": original_code,
        "final_code": current_code,
        "stdout": "",
        "stderr": current_stderr,
        "final_result": "Failed"
    }
