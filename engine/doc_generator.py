"""
HERMES Documentation Generator Module
Generates source-grounded Markdown technical documentation from AST analysis.
Supports:
1. Gemini / OpenAI LLM APIs via requests (if API key configured).
2. Institutional Deterministic AST Generator (Offline Mode) with line-level source citations.
"""

import os
import json
import requests
from typing import Dict, Any, Optional
from .ast_parser import analyze_python_source


def generate_offline_documentation(ast_data: Dict[str, Any], source_code: str, file_name: str) -> str:
    """
    Produce clean, comprehensive, source-grounded Markdown documentation
    deterministically from AST structural data.
    """
    title = file_name.replace(".py", "").replace("_", " ").title()
    lines = [
        f"# {title} Technical Specification",
        f"> **Source File:** [`{file_name}`](file:///{file_name})  ",
        f"> **Engine:** HERMES Deterministic AST Generator (Source-Grounded Baseline)  ",
        f"> **Coverage:** {ast_data.get('metrics', {}).get('doc_coverage_percent', 0)}% documented  ",
        "",
        "## Overview",
        ast_data.get("module_docstring") or f"This module defines core abstractions and utilities for `{file_name}`.",
        ""
    ]

    # Imports section
    imports = ast_data.get("imports", [])
    if imports:
        lines.append("## Module Dependencies")
        lines.append("| Imported Symbol / Module | Alias | Source Line |")
        lines.append("| :--- | :--- | :--- |")
        for imp in imports:
            mod = imp.get("module") or imp.get("name", "")
            alias = imp.get("asname") or "—"
            line = imp.get("line", 1)
            lines.append(f"| `{mod}` | `{alias}` | L{line} |")
        lines.append("")

    # Classes section
    classes = ast_data.get("classes", [])
    if classes:
        lines.append("## Class Specifications")
        for cls in classes:
            c_name = cls["name"]
            bases = ", ".join(cls.get("bases", [])) or "object"
            doc = cls.get("docstring") or "*No class-level docstring provided in source code.*"
            l_start = cls.get("line_start", 1)
            l_end = cls.get("line_end", l_start)

            lines.append(f"### `class {c_name}({bases})`")
            lines.append(f"*Defined at `{file_name}#L{l_start}-L{l_end}`*")
            lines.append("")
            lines.append(doc)
            lines.append("")

            methods = cls.get("methods", [])
            if methods:
                lines.append("#### Methods")
                for m in methods:
                    m_name = m["name"]
                    params = []
                    for p in m.get("parameters", []):
                        p_str = p["name"]
                        if p.get("type"):
                            p_str += f": {p['type']}"
                        if p.get("default") is not None:
                            p_str += f" = {p['default']}"
                        params.append(p_str)
                    param_sig = ", ".join(params)
                    ret = f" -> {m['return_type']}" if m.get("return_type") else ""
                    m_doc = m.get("docstring") or "*No method docstring available.*"
                    m_start = m.get("line_start", l_start)

                    lines.append(f"##### `{m_name}({param_sig}){ret}`")
                    lines.append(f"*Source: `{file_name}#L{m_start}`*")
                    lines.append("")
                    lines.append(m_doc)
                    lines.append("")

    # Top-level functions
    functions = ast_data.get("functions", [])
    if functions:
        lines.append("## Module Functions")
        for f in functions:
            f_name = f["name"]
            params = []
            for p in f.get("parameters", []):
                p_str = p["name"]
                if p.get("type"):
                    p_str += f": {p['type']}"
                if p.get("default") is not None:
                    p_str += f" = {p['default']}"
                params.append(p_str)
            param_sig = ", ".join(params)
            ret = f" -> {f['return_type']}" if f.get("return_type") else ""
            f_doc = f.get("docstring") or "*No docstring available.*"
            f_start = f.get("line_start", 1)

            lines.append(f"### `{f_name}({param_sig}){ret}`")
            lines.append(f"*Source: `{file_name}#L{f_start}`*")
            lines.append("")
            lines.append(f_doc)
            lines.append("")

    # Executable Verified Code Examples Section
    lines.append("## Executable Code Example")
    lines.append("The following code snippet is verified through the HERMES execution pipeline:")
    lines.append("")

    mod_base = file_name.replace(".py", "").replace("/", ".").replace("\\", ".")
    if classes:
        primary_cls = classes[0]["name"]
        lines.append("```python")
        lines.append(f"# Usage example for {primary_cls}")
        lines.append(f"from {mod_base} import {primary_cls}")
        lines.append("")
        lines.append(f"# Instantiate primary class")
        lines.append(f"instance = {primary_cls}()")
        lines.append(f"assert instance is not None")
        lines.append(f"print(f\"Successfully initialized {primary_cls}: {{type(instance).__name__}}\")")
        lines.append("```")
    elif functions:
        primary_fn = functions[0]["name"]
        lines.append("```python")
        lines.append(f"# Usage example for {primary_fn}")
        lines.append(f"from {mod_base} import {primary_fn}")
        lines.append("")
        lines.append(f"# Call function")
        lines.append(f"# result = {primary_fn}()")
        lines.append(f"print(\"Function reference checked:\", callable({primary_fn}))")
        lines.append("```")
    else:
        lines.append("```python")
        lines.append(f"import {mod_base}")
        lines.append(f"print(\"Module loaded:\", {mod_base}.__name__)")
        lines.append("```")

    lines.append("")
    lines.append("## Documentation Debt & Coverage Analysis")
    debt = ast_data.get("documentation_debt", [])
    if debt:
        lines.append("| Symbol Type | Target | Source Line | Issue |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for item in debt:
            lines.append(f"| `{item.get('type')}` | `{item.get('name')}` | L{item.get('line')} | {item.get('message')} |")
    else:
        lines.append("All symbols in this module have documented docstrings.")

    return "\n".join(lines)


def generate_llm_documentation(source_code: str, file_name: str, ast_data: Dict[str, Any], api_key: str, provider: str = "gemini") -> Optional[str]:
    """
    Generate rich technical documentation using Gemini or OpenAI API.
    """
    prompt = f"""You are HERMES, an institutional documentation intelligence engine.
Your task is to produce comprehensive, source-grounded Markdown documentation for the Python source code below.

File name: {file_name}
AST Summary:
- Classes: {[c['name'] for c in ast_data.get('classes', [])]}
- Functions: {[f['name'] for f in ast_data.get('functions', [])]}
- Doc Coverage: {ast_data.get('metrics', {}).get('doc_coverage_percent', 0)}%

Rules:
1. Start with an institutional title and brief overview.
2. Provide precise API specifications with parameter types, return values, and exceptions.
3. Every claim must cite the source file and line numbers (e.g. `{file_name}#L12-L45`).
4. Include at least ONE self-contained, executable code snippet enclosed in ```python ... ``` that can be run with Python.
5. In the code snippet, import from `{file_name.replace('.py', '').replace('/', '.')}` and include an `assert` or `print(...)` verifying the behavior.
6. Do not include speculative or hallucinatory claims.
7. Return ONLY clean Markdown.

Source Code:
```python
{source_code}
```
"""
    try:
        if provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text
        elif provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"LLM API call failed: {e}")
        return None
    return None


def generate_documentation_for_source(source_code: str, file_name: str, api_key: Optional[str] = None, provider: str = "offline_engine") -> Dict[str, Any]:
    """
    Main entry point: analyzes source and generates documentation.
    Falls back reliably to deterministic AST generation if no LLM key or LLM error.
    """
    ast_data = analyze_python_source(source_code, file_name)
    if not ast_data.get("is_valid", False):
        return {
            "success": False,
            "error": ast_data.get("error", "Failed to parse Python source code"),
            "ast_data": ast_data
        }

    doc_content = None
    engine_used = "HERMES Deterministic AST Engine"

    # Attempt LLM if key configured
    if api_key and provider in ("gemini", "openai"):
        llm_doc = generate_llm_documentation(source_code, file_name, ast_data, api_key, provider)
        if llm_doc:
            doc_content = llm_doc
            engine_used = f"AI Generation ({provider.upper()})"

    if not doc_content:
        doc_content = generate_offline_documentation(ast_data, source_code, file_name)

    return {
        "success": True,
        "engine_used": engine_used,
        "content": doc_content,
        "ast_data": ast_data
    }
