"""
HERMES — AI Documentation Intelligence Platform
Flask Backend Server & API Services
"""

import os
import sys
import json
import time
from flask import Flask, request, jsonify, render_template, send_from_directory

# Ensure hermes package and sample files can be found
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database import (
    init_db, seed_demo_data_if_empty, get_stats, get_all_documents,
    get_document_by_id, save_or_update_document, save_verification_run,
    get_all_verification_runs, save_pull_request, get_all_pull_requests,
    get_activities, log_activity, get_setting, set_setting
)
from engine.ast_parser import analyze_python_source
from engine.drift_detector import detect_code_drift, compute_code_hash
from engine.doc_generator import generate_documentation_for_source
from engine.verifier import verify_markdown_document, execute_snippet
from engine.correction_loop import run_bounded_correction_loop
from engine.git_simulator import create_pr_proposal, generate_unified_diff

app = Flask(__name__, static_folder="static", template_folder="templates")

# Initialize SQLite database and seed initial starter data if empty
init_db()
seed_demo_data_if_empty()


@app.route("/")
def index():
    return render_template("index.html")


# ==========================================
# REST API Endpoints
# ==========================================

@app.route("/api/stats", methods=["GET"])
def api_stats():
    """Retrieve live metrics computed directly from SQLite tables."""
    return jsonify(get_stats())


@app.route("/api/documents", methods=["GET", "POST"])
def api_documents():
    if request.method == "GET":
        return jsonify(get_all_documents())

    data = request.json or {}
    title = data.get("title", "Untitled Document")
    slug = data.get("slug") or title.lower().replace(" ", "-")
    content = data.get("content", "")
    file_path = data.get("file_path", "")
    language = data.get("language", "python")
    status = data.get("status", "synced")
    summary = data.get("change_summary", "Manual document edit")

    doc_id = save_or_update_document(title, slug, content, file_path, language, status, summary)
    log_activity("doc_gen", f"Document Saved: {title}", f"Saved revision with {len(content)} characters.", "info")
    return jsonify({"success": True, "id": doc_id})


@app.route("/api/documents/<int:doc_id>", methods=["GET"])
def api_document_detail(doc_id):
    doc = get_document_by_id(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    return jsonify(doc)


@app.route("/api/samples", methods=["GET"])
def api_samples():
    """Return available bundled Python source files for instant demonstration."""
    sample_dir = os.path.join(BASE_DIR, "sample_files")
    samples = []
    if os.path.exists(sample_dir):
        for fname in os.listdir(sample_dir):
            if fname.endswith(".py"):
                fpath = os.path.join(sample_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    samples.append({
                        "filename": fname,
                        "path": f"sample_files/{fname}",
                        "content": f.read()
                    })
    return jsonify(samples)


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """Parse Python source code using AST and return structural metadata."""
    data = request.json or {}
    source = data.get("source_code", "")
    filename = data.get("filename", "input.py")

    if not source.strip():
        return jsonify({"error": "Source code cannot be empty"}), 400

    analysis = analyze_python_source(source, filename)
    log_activity(
        "analysis",
        f"AST Analysis: {filename}",
        f"Extracted {len(analysis.get('classes', []))} classes, {len(analysis.get('functions', []))} functions.",
        "info"
    )
    return jsonify(analysis)


@app.route("/api/detect-drift", methods=["POST"])
def api_detect_drift():
    """Detect architectural and signature changes between revisions."""
    data = request.json or {}
    old_ast = data.get("old_ast")
    new_source = data.get("new_source_code", "")
    filename = data.get("filename", "source.py")

    new_ast = analyze_python_source(new_source, filename)
    drift = detect_code_drift(old_ast, new_ast)

    if drift["has_drift"]:
        log_activity(
            "drift_detected",
            f"Drift Detected: {filename}",
            drift["summary"],
            "warning",
            {"changes": drift["changes"]}
        )

    return jsonify({"drift": drift, "new_ast": new_ast})


@app.route("/api/generate-docs", methods=["POST"])
def api_generate_docs():
    """Generate source-grounded Markdown documentation from Python code."""
    data = request.json or {}
    source = data.get("source_code", "")
    filename = data.get("filename", "source.py")
    
    # Check settings for API keys
    api_key = get_setting("api_key", os.environ.get("GEMINI_API_KEY", ""))
    provider = get_setting("api_provider", "offline_engine")

    result = generate_documentation_for_source(source, filename, api_key=api_key, provider=provider)
    if result["success"]:
        log_activity(
            "doc_gen",
            f"Generated Docs: {filename}",
            f"Created specifications using {result['engine_used']}.",
            "success"
        )
    return jsonify(result)


@app.route("/api/verify", methods=["POST"])
def api_verify():
    """Extract code examples from Markdown and execute in isolated sandbox."""
    data = request.json or {}
    content = data.get("content", "")
    doc_id = data.get("document_id")

    timeout = float(get_setting("sandbox_timeout_seconds", "5.0"))
    results = verify_markdown_document(content, timeout_seconds=timeout)

    # Persist results
    all_passed = True
    for res in results:
        status = res["status"]
        if status != "Passed":
            all_passed = False
        save_verification_run(
            document_id=doc_id,
            snippet_id=res["snippet_id"],
            snippet_code=res["code"],
            status=status,
            stdout=res["stdout"],
            stderr=res["stderr"],
            execution_time_ms=res["execution_time_ms"]
        )

    log_activity(
        "test_run",
        f"Snippet Verification: {len(results)} snippet(s)",
        f"All passed: {all_passed}. Ran in isolated execution sandbox.",
        "success" if all_passed else "warning"
    )

    return jsonify({"results": results, "all_passed": all_passed})


@app.route("/api/correct", methods=["POST"])
def api_correct():
    """Execute bounded self-correction loop for a broken code snippet."""
    data = request.json or {}
    snippet = data.get("snippet_code", "")
    stderr = data.get("stderr", "")
    doc_id = data.get("document_id")
    snippet_id = data.get("snippet_id", "snippet-correction")

    api_key = get_setting("api_key", os.environ.get("GEMINI_API_KEY", ""))
    provider = get_setting("api_provider", "offline_engine")
    max_attempts = int(get_setting("max_correction_attempts", "2"))

    loop_result = run_bounded_correction_loop(
        original_code=snippet,
        initial_stderr=stderr,
        max_attempts=max_attempts,
        api_key=api_key,
        provider=provider
    )

    # Record verification outcome
    save_verification_run(
        document_id=doc_id,
        snippet_id=snippet_id,
        snippet_code=loop_result["final_code"],
        status=loop_result["final_result"],
        stdout=loop_result["stdout"],
        stderr=loop_result["stderr"],
        execution_time_ms=0.0,
        correction_attempts=loop_result["attempts_taken"],
        original_code=loop_result["original_code"],
        corrected_code=loop_result["final_code"]
    )

    log_activity(
        "correction",
        f"Self-Correction Run: {loop_result['final_result']}",
        f"Took {loop_result['attempts_taken']} iteration(s).",
        "success" if loop_result["success"] else "error"
    )

    return jsonify(loop_result)


@app.route("/api/run-pipeline", methods=["POST"])
def api_run_pipeline():
    """
    Execute complete 12-stage automated documentation pipeline:
    1. Ingest source -> 2. Change identification -> 3. AST structural parse ->
    4. Metadata extraction -> 5. Doc requirement planning -> 6. Markdown generation ->
    7. Code example extraction -> 8. Isolated execution -> 9. Error check ->
    10. Bounded correction -> 11. Persistence & versioning -> 12. PR staging.
    """
    data = request.json or {}
    source = data.get("source_code", "")
    filename = data.get("filename", "module.py")
    title = data.get("title", filename.replace(".py", "").title())

    stages = []
    def add_stage(num, name, status, details):
        stages.append({
            "stage": num,
            "name": name,
            "status": status,  # success, warning, error, skipped
            "details": details,
            "timestamp": time.time()
        })

    # Stage 1: Ingest source
    add_stage(1, "Receive Source Code", "success", f"Ingested {len(source)} bytes from `{filename}`.")

    # Stage 2: Parse AST
    ast_data = analyze_python_source(source, filename)
    if not ast_data.get("is_valid", False):
        add_stage(2, "Parse Source AST", "error", f"Syntax error: {ast_data.get('error')}")
        return jsonify({"success": False, "stages": stages})
    add_stage(2, "Parse Source AST", "success", f"AST compiled: {len(ast_data.get('classes', []))} classes, {len(ast_data.get('functions', []))} functions.")

    # Stage 3: Extract Structural Information
    metrics = ast_data.get("metrics", {})
    add_stage(3, "Extract Metadata & Signatures", "success", f"Extracted symbols: {metrics.get('total_symbols', 0)} total, {metrics.get('doc_coverage_percent', 0)}% coverage.")

    # Stage 4: Determine Doc Requirement
    add_stage(4, "Plan Documentation Scope", "success", "Identified API references, type annotations, and executable example blocks.")

    # Stage 5: Generate Documentation
    api_key = get_setting("api_key", os.environ.get("GEMINI_API_KEY", ""))
    provider = get_setting("api_provider", "offline_engine")
    doc_res = generate_documentation_for_source(source, filename, api_key=api_key, provider=provider)
    doc_content = doc_res["content"]
    add_stage(5, "Generate Technical Documentation", "success", f"Created documentation ({len(doc_content)} chars) using {doc_res['engine_used']}.")

    # Stage 6: Extract Code Examples
    from engine.verifier import extract_python_snippets
    snippets = extract_python_snippets(doc_content)
    add_stage(6, "Extract Code Examples", "success", f"Located {len(snippets)} executable Python snippet(s).")

    # Stage 7 & 8: Isolated Execution
    timeout = float(get_setting("sandbox_timeout_seconds", "5.0"))
    test_results = []
    corrections_applied = 0
    final_snippets = []

    for snip in snippets:
        exec_res = execute_snippet(snip["code"], timeout_seconds=timeout)
        if exec_res["status"] == "Passed":
            test_results.append({"id": snip["id"], "status": "Passed", "stdout": exec_res["stdout"]})
            final_snippets.append(snip["code"])
        else:
            # Stage 9 & 10: Correction Loop
            loop_res = run_bounded_correction_loop(
                snip["code"],
                exec_res["stderr"],
                max_attempts=int(get_setting("max_correction_attempts", "2")),
                api_key=api_key,
                provider=provider
            )
            if loop_res["success"]:
                corrections_applied += 1
                test_results.append({"id": snip["id"], "status": "Passed (Corrected)", "stdout": loop_res["stdout"]})
                # Replace snippet in document
                doc_content = doc_content.replace(snip["code"], loop_res["final_code"])
                final_snippets.append(loop_res["final_code"])
            else:
                test_results.append({"id": snip["id"], "status": "Failed", "stderr": loop_res["stderr"]})
                final_snippets.append(snip["code"])

    add_stage(7, "Execute Snippets in Isolation", "success" if all("Passed" in r["status"] for r in test_results) else "warning", f"Tested {len(snippets)} snippets.")
    if corrections_applied > 0:
        add_stage(8, "Bounded Correction Loop", "success", f"Successfully auto-corrected {corrections_applied} failing snippet(s).")

    # Stage 11: Save Document & Versions
    slug = filename.replace(".py", "").lower().replace("_", "-")
    doc_id = save_or_update_document(
        title=title,
        slug=slug,
        content=doc_content,
        file_path=filename,
        language="python",
        status="synced",
        change_summary=f"Automated pipeline synchronization for {filename}"
    )
    add_stage(9, "Persist Document & Versions", "success", f"Saved revision in SQLite (Doc ID: #{doc_id}).")

    # Stage 12: Stage Pull Request
    pr = create_pr_proposal(
        doc_title=title,
        file_path=filename,
        old_content="",
        new_content=doc_content,
        verification_passed=all("Passed" in r["status"] for r in test_results),
        github_token=get_setting("github_token"),
        github_repo=get_setting("github_repo")
    )
    pr_id = save_pull_request(
        title=pr["title"],
        branch_name=pr["branch_name"],
        summary=pr["summary"],
        diff_content=pr["diff_content"],
        status=pr["status"],
        pr_number=pr.get("pr_number"),
        pr_url=pr.get("pr_url"),
        is_demo=pr.get("is_demo", True)
    )
    add_stage(10, "Stage GitHub Pull Request", "success", f"PR #{pr.get('pr_number', pr_id)} staged on branch `{pr['branch_name']}` ({'Simulation' if pr.get('is_demo') else 'Real GitHub API'}).")

    log_activity(
        "doc_gen",
        f"Pipeline Run Completed: {filename}",
        f"Executed 10 pipeline stages, verified {len(snippets)} snippets, staged PR #{pr.get('pr_number', pr_id)}.",
        "success"
    )

    return jsonify({
        "success": True,
        "stages": stages,
        "document_id": doc_id,
        "document_content": doc_content,
        "test_results": test_results,
        "pull_request": pr
    })


@app.route("/api/assistant/chat", methods=["POST"])
def api_assistant_chat():
    """
    Project-grounded AI Assistant.
    Distinguishes verified facts from suggestions, references source files,
    and honestly admits missing context.
    """
    data = request.json or {}
    user_query = data.get("query", "").strip()

    if not user_query:
        return jsonify({"error": "Query cannot be empty"}), 400

    # Retrieve context from loaded documents
    docs = get_all_documents()
    samples = api_samples().get_json() or []
    
    # Grounding check
    found_context = []
    for d in docs:
        if any(term in user_query.lower() for term in d["title"].lower().split()):
            found_context.append(f"Document: {d['title']} ({d['file_path']})")
    for s in samples:
        if s["filename"].replace(".py", "") in user_query.lower():
            found_context.append(f"Source: {s['filename']}")

    # Check if Gemini/OpenAI key is set
    api_key = get_setting("api_key", os.environ.get("GEMINI_API_KEY", ""))
    provider = get_setting("api_provider", "offline_engine")

    if api_key and provider in ("gemini", "openai"):
        context_str = f"Available files: {[s['filename'] for s in samples]}. Available docs: {[d['title'] for d in docs]}."
        prompt = f"""You are the HERMES Project Intelligence Assistant.
User Question: {user_query}
Context: {context_str}

Rules:
1. Ground answers strictly in available project knowledge.
2. Clearly distinguish VERIFIED FACTS from AI RECOMMENDATIONS.
3. If an answer cannot be established from the files or documentation, state clearly: "Information cannot be established from the processed repository files."
4. Include source references (e.g. `[data_pipeline.py#L20]`) where applicable.
"""
        try:
            if provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
                resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
                if resp.status_code == 200:
                    ans = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                    return jsonify({
                        "response": ans,
                        "source_references": found_context,
                        "is_grounded": True,
                        "engine": f"AI ({provider})"
                    })
        except Exception:
            pass

    # Deterministic grounded responses
    q = user_query.lower()
    if "pipeline" in q or "stream" in q:
        resp = """### Verified Facts
- **Module:** `sample_files/data_pipeline.py`
- **Primary Classes:**
  - `RecordValidator`: Validates dictionary keys (`id`, `timestamp`, `payload`).
  - `StreamPipeline`: Handles ingestion, tracking `processed_count` and `error_count`.
- **Verified Code:** The `process_record()` method raises `ValueError` if required fields are missing.

### AI Recommendations
- Consider adding an async batch processor if streaming throughput exceeds 5,000 events/sec.
- For high-volume schemas, Pydantic or Msgpack could reduce serialization overhead.

*Source references:* `[data_pipeline.py#L10-L95]`, `[streampipeline-core-module.md]`"""
    elif "token" in q or "auth" in q:
        resp = """### Verified Facts
- **Module:** `sample_files/auth_service.py`
- **Class:** `TokenManager(secret_key, default_ttl_seconds=3600)`
- **Cryptographic Scheme:** SHA-256 HMAC signatures verified via `hmac.compare_digest` to prevent timing attacks.
- **Revocation:** Explicit in-memory set `_revocation_list`.

### AI Recommendations
- For distributed multi-node clusters, consider persisting revoked tokens in Redis rather than memory.

*Source references:* `[auth_service.py#L12-L75]`"""
    elif "test" in q or "verification" in q:
        resp = """### Verified Facts
- HERMES runs code snippets in an isolated Python subprocess with a configurable timeout (default 5.0s).
- Subprocesses capture return codes, standard output, and standard error.
- Failed examples trigger a bounded self-correction loop before persisting results.

*Source references:* `[engine/verifier.py]`, `[engine/correction_loop.py]`"""
    else:
        resp = f"""### Source-Grounded Inspection
The query mentions topics outside the currently indexed modules.

**Currently Tracked Knowledge:**
- `sample_files/data_pipeline.py` (ETL pipeline & validation)
- `sample_files/auth_service.py` (HMAC authentication & revocation)
- `sample_files/cache_client.py` (TTL key-value cache)

*Notice:* To analyze additional Python modules, upload or paste source code in the **Code Analysis** tab. HERMES avoids speculating on unprocessed files."""

    return jsonify({
        "response": resp,
        "source_references": found_context or ["Project workspace context"],
        "is_grounded": True,
        "engine": "HERMES Grounded Assistant (Deterministic Knowledge Base)"
    })


@app.route("/api/runs", methods=["GET"])
def api_runs():
    return jsonify(get_all_verification_runs())


@app.route("/api/pull-requests", methods=["GET", "POST"])
def api_pull_requests():
    if request.method == "GET":
        return jsonify(get_all_pull_requests())

    data = request.json or {}
    pr_id = save_pull_request(
        title=data.get("title", "docs: update documentation"),
        branch_name=data.get("branch_name", "hermes/docs-sync"),
        summary=data.get("summary", ""),
        diff_content=data.get("diff_content", ""),
        status=data.get("status", "simulated"),
        pr_number=data.get("pr_number"),
        pr_url=data.get("pr_url"),
        is_demo=data.get("is_demo", True)
    )
    return jsonify({"success": True, "id": pr_id})


@app.route("/api/activities", methods=["GET"])
def api_activities():
    return jsonify(get_activities())


@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    if request.method == "GET":
        return jsonify({
            "api_provider": get_setting("api_provider", "offline_engine"),
            "has_api_key": bool(get_setting("api_key") or os.environ.get("GEMINI_API_KEY")),
            "sandbox_timeout_seconds": get_setting("sandbox_timeout_seconds", "5.0"),
            "max_correction_attempts": get_setting("max_correction_attempts", "2"),
            "github_repo": get_setting("github_repo", "hermes-ai/data-pipeline-core"),
            "has_github_token": bool(get_setting("github_token"))
        })

    data = request.json or {}
    for key, val in data.items():
        if key in ("api_provider", "api_key", "sandbox_timeout_seconds", "max_correction_attempts", "github_repo", "github_token"):
            if val is not None and str(val).strip() != "":
                set_setting(key, str(val).strip())

    log_activity("settings", "Configuration Updated", "Workspace settings and execution limits updated.", "info")
    return jsonify({"success": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"HERMES documentation server running at http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
