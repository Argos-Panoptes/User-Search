"""
Ingestion pipeline test script.

Tests the full flow:
  1. Upload a file (chunked)
  2. Trigger ingestion (users / groups / avatars)
  3. Poll the job until done or timeout

Usage:
    python test_ingestion.py --type users --file /path/to/users.json
    python test_ingestion.py --type groups --file /path/to/groups.json
    python test_ingestion.py --type avatars --file /path/to/avatars.json
    python test_ingestion.py --type users --file /path/to/users.json --file-path-direct  # skip upload, pass file_path directly

Auth: set API_KEY or BEARER_TOKEN env var (needs superuser).
      Defaults to ENABLE_AUTH=False dev mode if neither is set.

Base URL: defaults to http://localhost:8000, override with BASE_URL env var.
"""

import argparse
import json
import math
import os
import sys
import time

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.environ.get("API_KEY", "")
BEARER_TOKEN = os.environ.get("BEARER_TOKEN", "")

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB
POLL_INTERVAL = 3  # seconds
POLL_TIMEOUT = 300  # seconds


def auth_headers() -> dict:
    if BEARER_TOKEN:
        return {"Authorization": f"Bearer {BEARER_TOKEN}"}
    if API_KEY:
        return {"X-API-Key": API_KEY}
    return {}


def upload_file(file_path: str) -> str:
    """Chunked upload. Returns upload_id."""
    file_size = os.path.getsize(file_path)
    total_chunks = max(1, math.ceil(file_size / CHUNK_SIZE))
    filename = os.path.basename(file_path)

    print(f"\n[upload] {filename} ({file_size:,} bytes, {total_chunks} chunk(s))")

    # Init
    resp = requests.post(
        f"{BASE_URL}/v1/uploads/init",
        json={"filename": filename, "total_chunks": total_chunks},
        headers=auth_headers(),
    )
    resp.raise_for_status()
    upload_id = resp.json()["upload_id"]
    print(f"[upload] upload_id = {upload_id}")

    # Upload chunks
    with open(file_path, "rb") as fh:
        for i in range(total_chunks):
            chunk = fh.read(CHUNK_SIZE)
            resp = requests.post(
                f"{BASE_URL}/v1/uploads/{upload_id}/chunk",
                data={"chunk_index": i},
                files={"file": (filename, chunk, "application/octet-stream")},
                headers=auth_headers(),
            )
            resp.raise_for_status()
            print(f"[upload] chunk {i + 1}/{total_chunks} ok")

    # Complete
    resp = requests.post(
        f"{BASE_URL}/v1/uploads/{upload_id}/complete",
        json={"filename": filename},
        headers=auth_headers(),
    )
    resp.raise_for_status()
    print(f"[upload] complete: {resp.json()}")
    return upload_id


def trigger_ingestion(ingest_type: str, upload_id: str = None, file_path: str = None) -> tuple[int, str]:
    """Trigger ingestion. Returns (job_id, task_id)."""
    payload = {}
    if upload_id:
        payload["upload_id"] = upload_id
    elif file_path:
        payload["file_path"] = file_path
    else:
        raise ValueError("Must provide upload_id or file_path")

    endpoint_map = {
        "users": "/v1/ingest/users",
        "groups": "/v1/ingest/groups",
        "avatars": "/v1/ingest/avatars",
    }
    url = BASE_URL + endpoint_map[ingest_type]

    print(f"\n[ingest] POST {url}  payload={payload}")
    resp = requests.post(url, json=payload, headers=auth_headers())

    if resp.status_code == 403:
        print("[ingest] ERROR 403 — superuser auth required. Set API_KEY or BEARER_TOKEN env var.")
        sys.exit(1)

    resp.raise_for_status()
    data = resp.json()
    print(f"[ingest] response: {json.dumps(data, indent=2)}")

    job_id = data.get("job_id") or data.get("data", {}).get("job_id")
    task_id = data.get("task_id") or data.get("data", {}).get("task_id")
    return job_id, task_id


def poll_job(job_id: int) -> dict:
    """Poll job status until terminal state or timeout."""
    print(f"\n[poll] watching job {job_id} (timeout {POLL_TIMEOUT}s)")
    deadline = time.time() + POLL_TIMEOUT
    terminal = {"completed", "failed", "error"}

    while time.time() < deadline:
        resp = requests.get(f"{BASE_URL}/v1/jobs/{job_id}", headers=auth_headers())
        resp.raise_for_status()
        job = resp.json().get("data") or resp.json()
        status = job.get("status", "unknown")
        steps = job.get("steps", [])
        step_summary = ", ".join(f"{s['step_name']}={s['status']}" for s in steps) if steps else "—"
        print(f"[poll] status={status}  steps=[{step_summary}]")

        if status in terminal:
            return job

        time.sleep(POLL_INTERVAL)

    print(f"[poll] TIMEOUT after {POLL_TIMEOUT}s — last status: {status}")
    return {}


def verify_results(ingest_type: str, job: dict):
    """Quick sanity check: search for anything after ingestion."""
    print(f"\n[verify] running a quick search to confirm data landed...")
    if ingest_type == "users":
        resp = requests.post(
            f"{BASE_URL}/v1/users/search",
            json={"limit": 5, "offset": 0},
            headers=auth_headers(),
        )
    elif ingest_type == "groups":
        resp = requests.post(
            f"{BASE_URL}/v1/groups/search",
            json={"limit": 5, "offset": 0},
            headers=auth_headers(),
        )
    else:
        print("[verify] skipping search check for avatars")
        return

    if resp.status_code == 200:
        data = resp.json()
        total = (
            data.get("pagination", {}).get("total")
            or data.get("total")
            or len(data.get("data", []))
        )
        print(f"[verify] search returned total={total} records ✓")
    else:
        print(f"[verify] search returned {resp.status_code}: {resp.text[:200]}")


def main():
    parser = argparse.ArgumentParser(description="Test ingestion pipeline end-to-end")
    parser.add_argument("--type", required=True, choices=["users", "groups", "avatars"], help="Ingestion type")
    parser.add_argument("--file", required=True, help="Path to JSON data file")
    parser.add_argument("--file-path-direct", action="store_true", help="Skip upload, send file_path directly (server must have access)")
    parser.add_argument("--no-poll", action="store_true", help="Trigger ingestion but don't wait for job completion")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"ERROR: file not found: {args.file}")
        sys.exit(1)

    print(f"=== Ingestion test: type={args.type}, base={BASE_URL} ===")

    if args.file_path_direct:
        job_id, task_id = trigger_ingestion(args.type, file_path=args.file)
    else:
        upload_id = upload_file(args.file)
        job_id, task_id = trigger_ingestion(args.type, upload_id=upload_id)

    if not job_id:
        print("[ERROR] No job_id in response — ingestion may not have started")
        sys.exit(1)

    print(f"\n[info] job_id={job_id}  task_id={task_id}")
    print(f"[info] track in UI or poll: GET {BASE_URL}/v1/jobs/{job_id}")

    if args.no_poll:
        print("[info] --no-poll set, exiting without waiting")
        return

    job = poll_job(job_id)

    if job.get("status") == "completed":
        print(f"\n[PASS] Job {job_id} completed successfully")
        metrics = job.get("metrics") or {}
        if metrics:
            print(f"  metrics: {json.dumps(metrics, indent=4)}")
        verify_results(args.type, job)
    elif job.get("status") in ("failed", "error"):
        print(f"\n[FAIL] Job {job_id} FAILED")
        print(f"  error: {job.get('error_message')}")
        steps = job.get("steps", [])
        failed_steps = [s for s in steps if s.get("status") in ("failed", "error")]
        for s in failed_steps:
            print(f"  failed step: {s.get('step_name')} — {s.get('error_message')}")
        sys.exit(1)
    else:
        print(f"\n? Job {job_id} ended with status: {job.get('status')}")


if __name__ == "__main__":
    main()
