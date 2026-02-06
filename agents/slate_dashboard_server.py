#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# CELL: slate_dashboard_server [python]
# Author: Claude | Created: 2026-02-06T23:45:00Z
# Purpose: SLATE Dashboard Server - FastAPI web interface for system monitoring
# ═══════════════════════════════════════════════════════════════════════════════
"""
SLATE Dashboard Server
======================
FastAPI server providing web UI for SLATE system monitoring.

Endpoints:
    GET  /              → Dashboard HTML
    GET  /health        → Health check
    GET  /api/status    → System status JSON
    GET  /api/tasks     → Task queue
    GET  /api/runner    → Runner status
    GET  /api/workflows → GitHub workflow status

Usage:
    python agents/slate_dashboard_server.py
    # Opens http://127.0.0.1:8080
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    print("[!] FastAPI/uvicorn not installed. Run: pip install fastapi uvicorn")
    sys.exit(1)

app = FastAPI(title="SLATE Dashboard", version="2.4.0")


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ─── System Status ────────────────────────────────────────────────────────────

@app.get("/api/status")
async def api_status():
    """Get full system status."""
    try:
        from slate.slate_status import get_status
        return JSONResponse(content=get_status())
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/tasks")
async def api_tasks():
    """Get current task queue."""
    task_file = WORKSPACE_ROOT / "current_tasks.json"
    if task_file.exists():
        try:
            tasks = json.loads(task_file.read_text(encoding="utf-8"))
            return JSONResponse(content=tasks)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)
    return JSONResponse(content={"tasks": []})


@app.get("/api/runner")
async def api_runner():
    """Get GitHub runner status."""
    try:
        from slate.slate_runner_manager import SlateRunnerManager
        manager = SlateRunnerManager()
        return JSONResponse(content=manager.detect())
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/workflows")
async def api_workflows():
    """Get GitHub workflow status."""
    try:
        gh_cli = WORKSPACE_ROOT / ".tools" / "gh.exe"
        if not gh_cli.exists():
            gh_cli = "gh"

        result = subprocess.run(
            [str(gh_cli), "run", "list", "--limit", "10", "--json", "name,status,conclusion,createdAt"],
            capture_output=True, text=True, timeout=10, cwd=str(WORKSPACE_ROOT)
        )
        if result.returncode == 0:
            return JSONResponse(content=json.loads(result.stdout))
        return JSONResponse(content={"error": result.stderr}, status_code=500)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/orchestrator")
async def api_orchestrator():
    """Get orchestrator status."""
    try:
        from slate.slate_orchestrator import SlateOrchestrator
        orch = SlateOrchestrator()
        return JSONResponse(content=orch.status())
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ─── Dashboard HTML ───────────────────────────────────────────────────────────

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SLATE Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', Consolas, monospace;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            background: linear-gradient(90deg, #4facfe, #00f2fe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .card {
            background: rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .card h2 {
            font-size: 1.2em;
            margin-bottom: 15px;
            color: #4facfe;
        }
        .status-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        .status-item:last-child { border-bottom: none; }
        .badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }
        .badge.online { background: rgba(0, 255, 128, 0.2); color: #00ff80; }
        .badge.offline { background: rgba(255, 80, 80, 0.2); color: #ff5050; }
        .badge.pending { background: rgba(255, 200, 0, 0.2); color: #ffc800; }
        .task-list { max-height: 300px; overflow-y: auto; }
        .task-item {
            padding: 10px;
            margin: 5px 0;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
        }
        .task-title { font-weight: 600; }
        .task-status { font-size: 0.85em; opacity: 0.7; }
        .refresh-btn {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #4facfe;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1em;
        }
        .refresh-btn:hover { background: #00f2fe; }
    </style>
</head>
<body>
    <div class="container">
        <h1>S.L.A.T.E.</h1>
        <div class="grid">
            <div class="card">
                <h2>System Status</h2>
                <div id="system-status">Loading...</div>
            </div>
            <div class="card">
                <h2>GitHub Runner</h2>
                <div id="runner-status">Loading...</div>
            </div>
            <div class="card">
                <h2>Recent Workflows</h2>
                <div id="workflows">Loading...</div>
            </div>
            <div class="card">
                <h2>Task Queue</h2>
                <div id="tasks" class="task-list">Loading...</div>
            </div>
        </div>
    </div>
    <button class="refresh-btn" onclick="refresh()">Refresh</button>

    <script>
        async function fetchStatus() {
            try {
                const res = await fetch('/api/orchestrator');
                const data = await res.json();
                document.getElementById('system-status').innerHTML = `
                    <div class="status-item">
                        <span>Orchestrator</span>
                        <span class="badge ${data.orchestrator?.running ? 'online' : 'offline'}">
                            ${data.orchestrator?.running ? 'Running' : 'Stopped'}
                        </span>
                    </div>
                    <div class="status-item">
                        <span>Dashboard</span>
                        <span class="badge online">Running</span>
                    </div>
                    <div class="status-item">
                        <span>Workflow</span>
                        <span class="badge ${data.workflow?.healthy ? 'online' : 'pending'}">
                            ${data.workflow?.task_count || 0} tasks
                        </span>
                    </div>
                `;
            } catch (e) {
                document.getElementById('system-status').innerHTML = 'Error loading status';
            }
        }

        async function fetchRunner() {
            try {
                const res = await fetch('/api/runner');
                const data = await res.json();
                const gpu = data.gpu_info || {};
                document.getElementById('runner-status').innerHTML = `
                    <div class="status-item">
                        <span>Status</span>
                        <span class="badge ${data.ready ? 'online' : 'offline'}">
                            ${data.ready ? 'Ready' : 'Not Ready'}
                        </span>
                    </div>
                    <div class="status-item">
                        <span>GPUs</span>
                        <span>${gpu.count || 0} detected</span>
                    </div>
                    <div class="status-item">
                        <span>GitHub</span>
                        <span class="badge ${data.github?.authenticated ? 'online' : 'offline'}">
                            ${data.github?.authenticated ? 'Connected' : 'Not Connected'}
                        </span>
                    </div>
                `;
            } catch (e) {
                document.getElementById('runner-status').innerHTML = 'Error loading runner status';
            }
        }

        async function fetchWorkflows() {
            try {
                const res = await fetch('/api/workflows');
                const data = await res.json();
                if (Array.isArray(data)) {
                    document.getElementById('workflows').innerHTML = data.slice(0, 5).map(w => `
                        <div class="status-item">
                            <span>${w.name}</span>
                            <span class="badge ${w.conclusion === 'success' ? 'online' : w.status === 'in_progress' ? 'pending' : 'offline'}">
                                ${w.conclusion || w.status}
                            </span>
                        </div>
                    `).join('');
                }
            } catch (e) {
                document.getElementById('workflows').innerHTML = 'Error loading workflows';
            }
        }

        async function fetchTasks() {
            try {
                const res = await fetch('/api/tasks');
                const data = await res.json();
                const tasks = data.tasks || data || [];
                if (Array.isArray(tasks) && tasks.length > 0) {
                    document.getElementById('tasks').innerHTML = tasks.slice(0, 10).map(t => `
                        <div class="task-item">
                            <div class="task-title">${t.title || t.name || 'Untitled'}</div>
                            <div class="task-status">${t.status || 'pending'}</div>
                        </div>
                    `).join('');
                } else {
                    document.getElementById('tasks').innerHTML = '<div class="task-item">No tasks</div>';
                }
            } catch (e) {
                document.getElementById('tasks').innerHTML = 'Error loading tasks';
            }
        }

        function refresh() {
            fetchStatus();
            fetchRunner();
            fetchWorkflows();
            fetchTasks();
        }

        refresh();
        setInterval(refresh, 30000);
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve dashboard HTML."""
    return DASHBOARD_HTML


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    """Run the dashboard server."""
    print()
    print("=" * 50)
    print("  SLATE Dashboard Server")
    print("=" * 50)
    print()
    print("  URL: http://127.0.0.1:8080")
    print()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8080,
        log_level="warning"
    )


if __name__ == "__main__":
    main()
