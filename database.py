"""
HERMES Database Layer (SQLite)
Provides persistent storage for documents, version history, test verification runs,
activity audit trails, settings, and staged pull requests.
"""

import sqlite3
import os
import json
import time
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hermes.db")


def get_db_connection():
    """Establish connection with row factory for dictionary-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create schema tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Documents table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        file_path TEXT,
        content TEXT NOT NULL,
        language TEXT DEFAULT 'python',
        status TEXT DEFAULT 'synced', -- synced, drift_detected, draft, archived
        version INTEGER DEFAULT 1,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    )
    """)

    # Document version history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS document_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        version_num INTEGER NOT NULL,
        content TEXT NOT NULL,
        change_summary TEXT,
        created_at REAL NOT NULL,
        FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
    )
    """)

    # Source files tracked
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS source_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT UNIQUE NOT NULL,
        filename TEXT NOT NULL,
        language TEXT DEFAULT 'python',
        content TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        ast_summary TEXT,
        last_analyzed_at REAL NOT NULL
    )
    """)

    # Verification and Test runs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS verification_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        snippet_id TEXT NOT NULL,
        snippet_code TEXT NOT NULL,
        language TEXT DEFAULT 'python',
        status TEXT NOT NULL, -- Passed, Failed, Pending, Not Tested
        stdout TEXT,
        stderr TEXT,
        execution_time_ms REAL,
        correction_attempts INTEGER DEFAULT 0,
        original_code TEXT,
        corrected_code TEXT,
        timestamp REAL NOT NULL,
        FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE SET NULL
    )
    """)

    # Pull Request proposals
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pull_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        branch_name TEXT NOT NULL,
        target_branch TEXT DEFAULT 'main',
        summary TEXT NOT NULL,
        diff_content TEXT NOT NULL,
        status TEXT DEFAULT 'draft', -- draft, simulated, opened, merged, closed
        pr_number INTEGER,
        pr_url TEXT,
        is_demo BOOLEAN DEFAULT 1,
        created_at REAL NOT NULL
    )
    """)

    # Chronological Activity Audit Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL, -- doc_gen, drift_detected, test_run, correction, pr_created, analysis
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        severity TEXT DEFAULT 'info', -- info, success, warning, error
        metadata_json TEXT,
        created_at REAL NOT NULL
    )
    """)

    # Settings
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


def log_activity(event_type: str, title: str, description: str, severity: str = "info", metadata: Optional[Dict[str, Any]] = None):
    """Record an audit trail event."""
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO activity_logs (event_type, title, description, severity, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event_type,
            title,
            description,
            severity,
            json.dumps(metadata or {}),
            time.time()
        ))
        conn.commit()
    finally:
        conn.close()


def get_activities(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve chronological activity events."""
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_stats() -> Dict[str, Any]:
    """Calculate live system statistics from real database tables."""
    conn = get_db_connection()
    try:
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        drift_count = conn.execute("SELECT COUNT(*) FROM documents WHERE status = 'drift_detected'").fetchone()[0]
        synced_count = conn.execute("SELECT COUNT(*) FROM documents WHERE status = 'synced'").fetchone()[0]
        
        runs_total = conn.execute("SELECT COUNT(*) FROM verification_runs").fetchone()[0]
        runs_passed = conn.execute("SELECT COUNT(*) FROM verification_runs WHERE status = 'Passed'").fetchone()[0]
        runs_failed = conn.execute("SELECT COUNT(*) FROM verification_runs WHERE status = 'Failed'").fetchone()[0]
        
        corrections_count = conn.execute("SELECT COUNT(*) FROM verification_runs WHERE correction_attempts > 0").fetchone()[0]
        pr_count = conn.execute("SELECT COUNT(*) FROM pull_requests").fetchone()[0]
        files_count = conn.execute("SELECT COUNT(*) FROM source_files").fetchone()[0]

        return {
            "documents_count": doc_count,
            "drift_count": drift_count,
            "synced_count": synced_count,
            "verification_total": runs_total,
            "verification_passed": runs_passed,
            "verification_failed": runs_failed,
            "correction_runs": corrections_count,
            "pull_requests_count": pr_count,
            "tracked_files": files_count,
            "verification_pass_rate": round((runs_passed / runs_total * 100), 1) if runs_total > 0 else 0.0
        }
    finally:
        conn.close()


def get_all_documents() -> List[Dict[str, Any]]:
    """Get list of all documents with metadata."""
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT id, title, slug, file_path, language, status, version, created_at, updated_at FROM documents ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_document_by_id(doc_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve complete document with content and versions."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            return None
        doc = dict(row)
        versions = conn.execute("SELECT id, version_num, change_summary, created_at FROM document_versions WHERE document_id = ? ORDER BY version_num DESC", (doc_id,)).fetchall()
        doc["versions"] = [dict(v) for v in versions]
        return doc
    finally:
        conn.close()


def save_or_update_document(title: str, slug: str, content: str, file_path: str = "", language: str = "python", status: str = "synced", change_summary: str = "Initial generation") -> int:
    """Save document and add version snapshot."""
    conn = get_db_connection()
    now = time.time()
    try:
        existing = conn.execute("SELECT id, version, content FROM documents WHERE slug = ?", (slug,)).fetchone()
        if existing:
            doc_id = existing["id"]
            new_version = existing["version"] + 1
            conn.execute("""
                UPDATE documents SET title = ?, content = ?, file_path = ?, language = ?, status = ?, version = ?, updated_at = ?
                WHERE id = ?
            """, (title, content, file_path, language, status, new_version, now, doc_id))
            
            conn.execute("""
                INSERT INTO document_versions (document_id, version_num, content, change_summary, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (doc_id, new_version, content, change_summary, now))
            conn.commit()
            return doc_id
        else:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO documents (title, slug, file_path, content, language, status, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (title, slug, file_path, content, language, status, now, now))
            doc_id = cur.lastrowid
            
            cur.execute("""
                INSERT INTO document_versions (document_id, version_num, content, change_summary, created_at)
                VALUES (?, 1, ?, ?, ?)
            """, (doc_id, content, change_summary, now))
            conn.commit()
            return doc_id
    finally:
        conn.close()


def save_verification_run(document_id: Optional[int], snippet_id: str, snippet_code: str, status: str, stdout: str, stderr: str, execution_time_ms: float, correction_attempts: int = 0, original_code: str = "", corrected_code: str = "") -> int:
    """Record snippet execution test outcome."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO verification_runs (
                document_id, snippet_id, snippet_code, status, stdout, stderr,
                execution_time_ms, correction_attempts, original_code, corrected_code, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            document_id, snippet_id, snippet_code, status, stdout, stderr,
            execution_time_ms, correction_attempts, original_code, corrected_code, time.time()
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_all_verification_runs(limit: int = 40) -> List[Dict[str, Any]]:
    """Retrieve recent test verification executions."""
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT v.*, d.title as document_title
            FROM verification_runs v
            LEFT JOIN documents d ON v.document_id = d.id
            ORDER BY v.timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_pull_request(title: str, branch_name: str, summary: str, diff_content: str, status: str = "simulated", pr_number: Optional[int] = None, pr_url: Optional[str] = None, is_demo: bool = True) -> int:
    """Stage a pull request update."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pull_requests (
                title, branch_name, summary, diff_content, status, pr_number, pr_url, is_demo, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, branch_name, summary, diff_content, status, pr_number, pr_url, is_demo, time.time()
        ))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_all_pull_requests() -> List[Dict[str, Any]]:
    """Retrieve staged and created pull requests."""
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM pull_requests ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Fetch setting value."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str):
    """Store or update setting value."""
    conn = get_db_connection()
    try:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
    finally:
        conn.close()


def seed_demo_data_if_empty():
    """Populate realistic starter documents, tests, and audit trail if empty."""
    conn = get_db_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        if count > 0:
            return  # Already populated

        # Seed initial settings
        set_setting("api_provider", "offline_engine")
        set_setting("sandbox_timeout_seconds", "5")
        set_setting("max_correction_attempts", "2")
        set_setting("github_repo", "hermes-ai/data-pipeline-core")

        # 1. Seed data_pipeline document
        doc1_content = """# StreamPipeline API Reference
`hermes.data_pipeline.StreamPipeline`

The `StreamPipeline` class coordinates real-time stream transformation, record validation, and operational metrics collection.

## Class Overview

```python
class StreamPipeline(name: str, batch_size: int = 100)
```

### Parameters
- `name` (*str*): Unique human-readable pipeline label for tracking metrics.
- `batch_size` (*int*, default: `100`): Chunk size threshold for batch ingestion.

## Verified Code Example

```python
from sample_files.data_pipeline import StreamPipeline

pipeline = StreamPipeline("analytics_stream", batch_size=50)
record = {"id": "REC-101", "timestamp": 1700000000, "payload": {"cpu": 42.1}}
result = pipeline.process_record(record)

assert result["status"] == "VERIFIED"
assert "processed_at" in result
print(f"Pipeline status: {result['status']}, processed {pipeline.processed_count} records.")
```

## Methods

### `process_record(record: Dict[str, Any]) -> Dict[str, Any]`
Validates the input dictionary against `RecordValidator` schema rules. Stamps `processed_at` unix timestamp and returns the enriched structure.

Raises:
- `ValueError`: When missing required keys (`id`, `timestamp`, `payload`).

### `batch_process(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]`
Iterates over a list of records. Isolates failures: invalid records are skipped while valid records are processed and returned.

### `get_metrics() -> Dict[str, Any]`
Returns operational throughput statistics including `processed`, `errors`, and computed `success_rate`.
"""
        doc1_id = save_or_update_document(
            title="StreamPipeline Core Module",
            slug="streampipeline-core-module",
            content=doc1_content,
            file_path="sample_files/data_pipeline.py",
            language="python",
            status="synced",
            change_summary="Initial source-grounded documentation generated from AST parse"
        )

        # 2. Seed auth_service document
        doc2_content = """# TokenManager Authentication Specification
`hermes.auth_service.TokenManager`

Cryptographic authentication utility providing signed HMAC token generation and expiration management.

## Specification

```python
class TokenManager(secret_key: str, default_ttl_seconds: int = 3600)
```

## Verified Code Example

```python
from sample_files.auth_service import TokenManager

manager = TokenManager(secret_key="production_secret_key_9918", default_ttl_seconds=3600)
token = manager.generate_token(user_id="usr_8821a", role="engineer")
payload = manager.verify_token(token)

assert payload is not None
assert payload["user_id"] == "usr_8821a"
assert payload["role"] == "engineer"
print(f"Token verified for user {payload['user_id']} with role {payload['role']}")
```

## Security Guarantees
- Employs SHA-256 HMAC for forgery resistance.
- Constant-time signature comparison using `hmac.compare_digest` to prevent timing attacks.
- Explicit token revocation registry for instant invalidation.
"""
        doc2_id = save_or_update_document(
            title="TokenManager Auth Specification",
            slug="tokenmanager-auth-specification",
            content=doc2_content,
            file_path="sample_files/auth_service.py",
            language="python",
            status="synced",
            change_summary="Generated from source AST with cryptographic guarantees"
        )

        # 3. Seed verification runs
        save_verification_run(
            document_id=doc1_id,
            snippet_id="streampipeline-example-1",
            snippet_code='from sample_files.data_pipeline import StreamPipeline\n\npipeline = StreamPipeline("analytics_stream")\nresult = pipeline.process_record({"id": "REC-1", "timestamp": 123, "payload": {}})\nassert result["status"] == "VERIFIED"\nprint("Pipeline status: OK")',
            status="Passed",
            stdout="Pipeline status: OK\n",
            stderr="",
            execution_time_ms=18.4,
            correction_attempts=0
        )

        save_verification_run(
            document_id=doc2_id,
            snippet_id="tokenmanager-example-1",
            snippet_code='from sample_files.auth_service import TokenManager\n\nmanager = TokenManager("secret")\ntoken = manager.generate_token("u1", "admin")\nassert manager.verify_token(token)["role"] == "admin"\nprint("Auth token verified")',
            status="Passed",
            stdout="Auth token verified\n",
            stderr="",
            execution_time_ms=12.2,
            correction_attempts=0
        )

        # 4. Seed an example that was corrected
        save_verification_run(
            document_id=doc1_id,
            snippet_id="streampipeline-example-2-batch",
            snippet_code='from sample_files.data_pipeline import StreamPipeline\n\npipeline = StreamPipeline("test")\nout = pipeline.batch_process([{"id": "1", "timestamp": 100, "payload": "ok"}])\nassert len(out) == 1\nprint("Batch complete")',
            status="Passed",
            stdout="Batch complete\n",
            stderr="",
            execution_time_ms=22.1,
            correction_attempts=1,
            original_code='from sample_files.data_pipeline import StreamPipeline\npipeline = StreamPipeline("test")\n# missing payload field\nout = pipeline.process_record({"id": "1", "timestamp": 100})\nprint("Done")',
            corrected_code='from sample_files.data_pipeline import StreamPipeline\n\npipeline = StreamPipeline("test")\nout = pipeline.batch_process([{"id": "1", "timestamp": 100, "payload": "ok"}])\nassert len(out) == 1\nprint("Batch complete")'
        )

        # 5. Seed pull request
        diff_text = """diff --git a/docs/streampipeline.md b/docs/streampipeline.md
--- a/docs/streampipeline.md
+++ b/docs/streampipeline.md
@@ -10,3 +10,5 @@
+## Methods
+### `batch_process(records)`
+Iterates over records with error isolation.
"""
        save_pull_request(
            title="docs(pipeline): update StreamPipeline specification and add batch_process",
            branch_name="hermes/doc-sync-streampipeline",
            summary="Automatically generated synchronization PR following update to sample_files/data_pipeline.py",
            diff_content=diff_text,
            status="simulated",
            pr_number=104,
            pr_url="https://github.com/hermes-ai/data-pipeline-core/pull/104",
            is_demo=True
        )

        # 6. Seed audit log
        log_activity("analysis", "Source AST Parsed", "Parsed sample_files/data_pipeline.py (Classes: 2, Methods: 5)", "info")
        log_activity("doc_gen", "Documentation Generated", "Generated specification for StreamPipeline Core Module", "success")
        log_activity("test_run", "Snippet Verification Passed", "Verified 2 executable snippets across 2 documents", "success")
        log_activity("correction", "Self-Correction Applied", "Resolved ValueError in batch_process snippet after 1 iteration", "info")
        log_activity("pr_created", "Pull Request Staged", "Staged PR #104 (branch: hermes/doc-sync-streampipeline)", "info")

    finally:
        conn.close()
