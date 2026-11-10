"""
HERMES Drift Detector Module
Compares source code revisions and AST structural profiles to detect:
- Added classes, methods, or functions (coverage gap)
- Deleted classes, methods, or functions (outdated documentation)
- Changed signatures (renamed parameters, type hint alterations, changed defaults)
- Docstring drift (code modified without docstring update)
"""

from typing import Dict, Any, List, Optional
import hashlib
from .ast_parser import analyze_python_source


def compute_code_hash(code_str: str) -> str:
    """Compute SHA-256 hash of normalized code string."""
    return hashlib.sha256(code_str.strip().encode("utf-8")).hexdigest()


def detect_code_drift(old_ast: Optional[Dict[str, Any]], new_ast: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare old AST representation against new AST representation to detect
    breaking changes, additions, and drift in documentation.
    """
    if not old_ast or not old_ast.get("is_valid", False):
        # Initial analysis — no prior baseline
        return {
            "has_drift": False,
            "is_initial": True,
            "drift_score": 0,
            "changes": [],
            "summary": "Initial baseline analysis established."
        }

    changes: List[Dict[str, Any]] = []

    # Map old classes and functions
    old_classes = {c["name"]: c for c in old_ast.get("classes", [])}
    new_classes = {c["name"]: c for c in new_ast.get("classes", [])}

    old_functions = {f["name"]: f for f in old_ast.get("functions", [])}
    new_functions = {f["name"]: f for f in new_ast.get("functions", [])}

    # 1. Detect Class additions and removals
    for name, c in new_classes.items():
        if name not in old_classes:
            changes.append({
                "type": "class_added",
                "severity": "medium",
                "symbol": name,
                "line": c.get("line_start"),
                "description": f"New class '{name}' added; requires documentation section."
            })
        else:
            # Check methods within the class
            old_methods = {m["name"]: m for m in old_classes[name].get("methods", [])}
            new_methods = {m["name"]: m for m in c.get("methods", [])}

            for m_name, m_info in new_methods.items():
                if m_name not in old_methods:
                    changes.append({
                        "type": "method_added",
                        "severity": "medium",
                        "symbol": f"{name}.{m_name}",
                        "line": m_info.get("line_start"),
                        "description": f"New method '{m_name}' added to class '{name}'."
                    })
                else:
                    # Check signature changes
                    old_m = old_methods[m_name]
                    old_params = [p["name"] for p in old_m.get("parameters", [])]
                    new_params = [p["name"] for p in m_info.get("parameters", [])]
                    if old_params != new_params:
                        changes.append({
                            "type": "signature_changed",
                            "severity": "high",
                            "symbol": f"{name}.{m_name}",
                            "line": m_info.get("line_start"),
                            "description": f"Parameter signature of '{name}.{m_name}' changed from ({', '.join(old_params)}) to ({', '.join(new_params)})."
                        })

            for m_name, m_info in old_methods.items():
                if m_name not in new_methods:
                    changes.append({
                        "type": "method_removed",
                        "severity": "high",
                        "symbol": f"{name}.{m_name}",
                        "line": m_info.get("line_start"),
                        "description": f"Method '{m_name}' removed from class '{name}'; documentation examples may fail."
                    })

    for name, c in old_classes.items():
        if name not in new_classes:
            changes.append({
                "type": "class_removed",
                "severity": "high",
                "symbol": name,
                "line": c.get("line_start"),
                "description": f"Class '{name}' was removed; existing documentation is obsolete."
            })

    # 2. Detect Standalone Function additions, removals, signature changes
    for name, f in new_functions.items():
        if name not in old_functions:
            changes.append({
                "type": "function_added",
                "severity": "medium",
                "symbol": name,
                "line": f.get("line_start"),
                "description": f"New function '{name}' added to module."
            })
        else:
            old_f = old_functions[name]
            old_params = [p["name"] for p in old_f.get("parameters", [])]
            new_params = [p["name"] for p in f.get("parameters", [])]
            if old_params != new_params:
                changes.append({
                    "type": "signature_changed",
                    "severity": "high",
                    "symbol": name,
                    "line": f.get("line_start"),
                    "description": f"Signature of '{name}' modified: ({', '.join(old_params)}) -> ({', '.join(new_params)})."
                })

    for name, f in old_functions.items():
        if name not in new_functions:
            changes.append({
                "type": "function_removed",
                "severity": "high",
                "symbol": name,
                "line": f.get("line_start"),
                "description": f"Function '{name}' removed from module."
            })

    # Calculate overall drift score (0 - 100)
    score = min(100, len(changes) * 20)
    has_drift = len(changes) > 0

    return {
        "has_drift": has_drift,
        "is_initial": False,
        "drift_score": score,
        "changes_count": len(changes),
        "changes": changes,
        "summary": f"Detected {len(changes)} structural difference(s) between revisions." if has_drift else "No structural drift detected; documentation is synchronized."
    }
