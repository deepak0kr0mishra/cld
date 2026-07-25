const form = document.querySelector("#scrapeForm");
const runButton = document.querySelector("#runButton");
const statusPill = document.querySelector("#statusPill");
const checkedCount = document.querySelector("#checkedCount");
const recordCount = document.querySelector("#recordCount");
const failureCount = document.querySelector("#failureCount");
const currentReg = document.querySelector("#currentReg");
const progressLabel = document.querySelector("#progressLabel");
const progressPercent = document.querySelector("#progressPercent");
const progressFill = document.querySelector("#progressFill");
const resultsBody = document.querySelector("#resultsBody");
const downloadButton = document.querySelector("#downloadButton");

let pollTimer = null;
let latestResults = [];

function setStatus(text, mode = "") {
    statusPill.textContent = text;
    statusPill.className = `status-pill ${mode}`.trim();
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function sgpaValue(record) {
    if (Array.isArray(record.sgpa)) {
        return record.sgpa.find((item) => item && item !== "-") || "-";
    }
    return record.sgpa || "-";
}

function isSuccess(record) {
    return record && !record.status && (record.name || record.redg_no);
}

function renderResults(results) {
    latestResults = results || [];
    downloadButton.disabled = latestResults.length === 0;

    if (!latestResults.length) {
        resultsBody.innerHTML = `<tr class="empty-row"><td colspan="7">No results yet.</td></tr>`;
        return;
    }

    resultsBody.innerHTML = latestResults.map((record) => {
        const ok = isSuccess(record);
        const regNo = record.redg_no || record.regNo || "-";
        const name = record.name || "-";
        const college = record.college_name || "-";
        const course = record.course || "-";
        const sgpa = sgpaValue(record);
        const cgpa = record.cgpa || "-";
        const status = ok ? "Found" : (record.message || record.status || "Failed");
        const statusClass = ok ? "status-ok" : "status-fail";

        return `
            <tr>
                <td>${escapeHtml(regNo)}</td>
                <td>${escapeHtml(name)}</td>
                <td>${escapeHtml(college)}</td>
                <td>${escapeHtml(course)}</td>
                <td>${escapeHtml(sgpa)}</td>
                <td>${escapeHtml(cgpa)}</td>
                <td><span class="${statusClass}">${escapeHtml(status)}</span></td>
            </tr>
        `;
    }).join("");
}

function updateStats(job) {
    const results = job.results || [];
    const failures = results.filter((record) => !isSuccess(record)).length;
    const checked = job.current || results.length || 0;
    const total = job.total || 135;
    const percent = Math.min(100, Math.round((checked / total) * 100));

    checkedCount.textContent = checked;
    recordCount.textContent = results.length;
    failureCount.textContent = failures;
    currentReg.textContent = job.currentRegNo || "-";
    progressPercent.textContent = `${percent}%`;
    progressFill.style.width = `${percent}%`;

    if (job.status === "running") {
        progressLabel.textContent = job.currentRegNo ? `Scanning ${job.currentRegNo}` : "Starting browser";
        setStatus("Running", "running");
        runButton.disabled = true;
    } else if (job.status === "finished") {
        progressLabel.textContent = job.stopReason || "Finished";
        setStatus("Finished");
        runButton.disabled = false;
    } else if (job.status === "failed") {
        progressLabel.textContent = job.error || "Failed";
        setStatus("Failed", "failed");
        runButton.disabled = false;
    } else {
        progressLabel.textContent = "Queued";
        setStatus("Queued", "running");
        runButton.disabled = true;
    }

    renderResults(results);
}

async function pollJob(jobId) {
    const response = await fetch(`/api/jobs/${jobId}`);
    const job = await response.json();

    if (!response.ok) {
        throw new Error(job.error || "Unable to load job.");
    }

    updateStats(job);

    if (job.status === "finished" || job.status === "failed") {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearInterval(pollTimer);
    pollTimer = null;

    const data = Object.fromEntries(new FormData(form).entries());
    runButton.disabled = true;
    setStatus("Queued", "running");
    progressLabel.textContent = "Creating job";
    progressFill.style.width = "0%";
    progressPercent.textContent = "0%";
    renderResults([]);

    try {
        const response = await fetch("/api/jobs", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(data),
        });
        const body = await response.json();

        if (!response.ok) {
            throw new Error(body.error || "Could not start scrape.");
        }

        await pollJob(body.jobId);
        pollTimer = setInterval(() => {
            pollJob(body.jobId).catch((error) => {
                clearInterval(pollTimer);
                pollTimer = null;
                progressLabel.textContent = error.message;
                setStatus("Failed", "failed");
                runButton.disabled = false;
            });
        }, 1600);
    } catch (error) {
        progressLabel.textContent = error.message;
        setStatus("Failed", "failed");
        runButton.disabled = false;
    }
});

downloadButton.addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(latestResults, null, 2)], {type: "application/json"});
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "beu-results.json";
    link.click();
    URL.revokeObjectURL(link.href);
});
