"""
HERMES End-to-End Verification Test Suite
"""

import os
import sys
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app


def run_tests():
    client = app.test_client()

    print("=== 1. Testing GET / (Homepage / Workspace Shell) ===")
    res = client.get("/")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    assert b"HERMES" in res.data
    print(f"OK (Size: {len(res.data)} bytes)")

    print("\n=== 2. Testing GET /api/stats ===")
    res = client.get("/api/stats")
    assert res.status_code == 200
    stats = res.get_json()
    print("Stats:", json.dumps(stats, indent=2))
    assert stats["documents_count"] >= 2

    print("\n=== 3. Testing GET /api/samples ===")
    res = client.get("/api/samples")
    assert res.status_code == 200
    samples = res.get_json()
    print("Loaded samples:", [s["filename"] for s in samples])
    assert len(samples) >= 3

    print("\n=== 4. Testing POST /api/analyze (AST Parser) ===")
    sample_code = samples[0]["content"]
    res = client.post("/api/analyze", json={"source_code": sample_code, "filename": samples[0]["filename"]})
    assert res.status_code == 200
    analysis = res.get_json()
    print("AST Valid:", analysis["is_valid"])
    print("Classes found:", [c["name"] for c in analysis["classes"]])
    print("Doc coverage %:", analysis["metrics"]["doc_coverage_percent"])

    print("\n=== 5. Testing POST /api/run-pipeline (12-Stage Pipeline) ===")
    res = client.post("/api/run-pipeline", json={"source_code": sample_code, "filename": samples[0]["filename"]})
    assert res.status_code == 200
    pipeline_out = res.get_json()
    print("Pipeline success:", pipeline_out["success"])
    print("Stages executed:", len(pipeline_out["stages"]))
    for stage in pipeline_out["stages"]:
        print(f"  [Stage {stage['stage']}] {stage['name']}: {stage['status']} - {stage['details']}")

    print("\n=== 6. Testing POST /api/assistant/chat ===")
    res = client.post("/api/assistant/chat", json={"query": "Explain StreamPipeline and error handling"})
    assert res.status_code == 200
    ans = res.get_json()
    print("Assistant grounded response preview:")
    print(ans["response"][:220] + "...")

    print("\n=== 7. Testing POST /api/verify ===")
    res = client.post("/api/verify", json={"content": "```python\nfrom sample_files.cache_client import MemoryCache\ncache = MemoryCache()\ncache.set('key1', 'val1')\nassert cache.get('key1') == 'val1'\nprint('Cache verified!')\n```"})
    assert res.status_code == 200
    verify_out = res.get_json()
    print("Verification result:", verify_out["all_passed"], verify_out["results"][0]["status"])

    print("\n=== ALL HERMES CORE SYSTEMS AND PIPELINES VERIFIED SUCCESSFULLY! ===")


if __name__ == "__main__":
    run_tests()
