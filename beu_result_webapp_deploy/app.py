import threading
import uuid
from datetime import datetime
import os

from flask import Flask, jsonify, render_template, request

from scraper import END_ROLL, MAX_CONSECUTIVE_NOT_FOUND, START_ROLL, scrape_results


app = Flask(__name__)

jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def serialize_error(message: str, status_code: int = 400):
    return jsonify({"error": message}), status_code


def run_job(job_id: str, payload: dict) -> None:
    def on_progress(event: dict) -> None:
        with jobs_lock:
            job = jobs[job_id]
            job["updatedAt"] = now_iso()
            job["lastEvent"] = event
            job["logs"].append(event)
            if event.get("type") == "processing":
                job["current"] = event.get("current", job["current"])
                job["total"] = event.get("total", job["total"])
                job["currentRegNo"] = event.get("regNo")
            if event.get("type") == "record":
                record = event.get("record")
                if record:
                    job["results"].append(record)
                job["consecutiveFailures"] = event.get(
                    "consecutiveFailures", job["consecutiveFailures"]
                )
            if event.get("type") == "stopping":
                job["stopReason"] = event.get("message")

    with jobs_lock:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["updatedAt"] = now_iso()

    try:
        results = scrape_results(
            college_code=payload["collegeCode"],
            year=payload["year"],
            branch_code=payload["branchCode"],
            start_roll=START_ROLL,
            end_roll=END_ROLL,
            max_consecutive_not_found=MAX_CONSECUTIVE_NOT_FOUND,
            output_filename="beu_bulk_automation_results.json",
            progress_callback=on_progress,
        )
        with jobs_lock:
            jobs[job_id]["status"] = "finished"
            jobs[job_id]["results"] = results
            jobs[job_id]["updatedAt"] = now_iso()
    except Exception as exc:
        with jobs_lock:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(exc)
            jobs[job_id]["updatedAt"] = now_iso()


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/jobs")
def create_job():
    data = request.get_json(silent=True) or {}
    payload = {
        "collegeCode": str(data.get("collegeCode", "")).strip(),
        "year": str(data.get("year", "")).strip(),
        "branchCode": str(data.get("branchCode", "")).strip(),
    }

    if not payload["collegeCode"] or not payload["year"] or not payload["branchCode"]:
        return serialize_error("College code, year, and branch code are required.")

    with jobs_lock:
        active_job = next((job for job in jobs.values() if job["status"] == "running"), None)
        if active_job:
            return serialize_error("A scrape is already running. Wait for it to finish.", 409)

        job_id = uuid.uuid4().hex
        jobs[job_id] = {
            "id": job_id,
            "status": "queued",
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
            "params": payload,
            "current": 0,
            "total": END_ROLL - START_ROLL + 1,
            "currentRegNo": None,
            "consecutiveFailures": 0,
            "stopReason": None,
            "results": [],
            "logs": [],
            "error": None,
        }

    thread = threading.Thread(target=run_job, args=(job_id, payload), daemon=True)
    thread.start()
    return jsonify({"jobId": job_id})


@app.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return serialize_error("Job not found.", 404)
        return jsonify(job)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
