#!/usr/bin/env python3
"""
# Modified: 2026-02-07T23:00:00Z | Author: COPILOT | Change: Create dependency fork manager

SLATE Dependency Fork Manager

Manages organizational forks of SLATE's upstream dependencies under the
SynchronizedLivingArchitecture GitHub org. Each fork tracks its upstream
and is monitored for drift.

Usage:
    python slate/slate_dependency_forks.py --status          # Show all fork statuses
    python slate/slate_dependency_forks.py --check           # Check upstream drift
    python slate/slate_dependency_forks.py --fork <owner/repo>  # Fork a new dependency
    python slate/slate_dependency_forks.py --sync <repo>     # Sync fork with upstream
    python slate/slate_dependency_forks.py --sync-all        # Sync all forks
    python slate/slate_dependency_forks.py --init            # Fork all tracked dependencies
    python slate/slate_dependency_forks.py --json            # JSON output

Security:
    - All API calls use git credential manager (no hardcoded tokens)
    - Local-only operations bind to 127.0.0.1
    - No eval/exec patterns
"""

import argparse
import json
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Optional

WORKSPACE = Path(__file__).parent.parent
ORG = "SynchronizedLivingArchitecture"
API_BASE = "https://api.github.com"

# ═══════════════════════════════════════════════════════════════════════════════
# SLATE Dependency Registry
# Each entry: upstream owner/repo → purpose, category, priority
# ═══════════════════════════════════════════════════════════════════════════════

DEPENDENCY_FORKS = {
    # ── Core Runtime ──────────────────────────────────────────────────────
    "microsoft/vscode": {
        "purpose": "VS Code API — extension host, chat participant API, LM tools API",
        "category": "core",
        "priority": "high",
        "track": ["releases", "tags"],
        "paths_of_interest": [
            "src/vscode-dts/",
            "src/vs/workbench/contrib/chat/",
            "src/vs/workbench/api/common/extHostLanguageModels.ts",
        ],
    },
    "ollama/ollama": {
        "purpose": "Local LLM inference engine — SLATE model serving",
        "category": "core",
        "priority": "high",
        "track": ["releases"],
        "paths_of_interest": [
            "api/",
            "gpu/",
            "llm/",
        ],
    },
    "chroma-core/chroma": {
        "purpose": "ChromaDB vector store — RAG memory and codebase embeddings",
        "category": "core",
        "priority": "high",
        "track": ["releases"],
        "paths_of_interest": [
            "chromadb/api/",
            "chromadb/config.py",
        ],
    },

    # ── Web / API ─────────────────────────────────────────────────────────
    "fastapi/fastapi": {
        "purpose": "Dashboard server framework (127.0.0.1:8080)",
        "category": "web",
        "priority": "medium",
        "track": ["releases"],
        "paths_of_interest": [
            "fastapi/",
        ],
    },
    "Kludex/uvicorn": {
        "purpose": "ASGI server for dashboard",
        "category": "web",
        "priority": "medium",
        "track": ["releases"],
        "paths_of_interest": [],
    },

    # ── AI / ML ───────────────────────────────────────────────────────────
    "huggingface/transformers": {
        "purpose": "Transformer models — optional local AI inference",
        "category": "ai",
        "priority": "medium",
        "track": ["releases"],
        "paths_of_interest": [
            "src/transformers/generation/",
            "src/transformers/models/mistral/",
            "src/transformers/models/llama/",
        ],
    },
    "pytorch/pytorch": {
        "purpose": "GPU compute — CUDA inference on dual RTX 5070 Ti",
        "category": "ai",
        "priority": "high",
        "track": ["releases"],
        "paths_of_interest": [
            "torch/cuda/",
            "torch/nn/",
        ],
    },
    "huggingface/accelerate": {
        "purpose": "Multi-GPU model distribution",
        "category": "ai",
        "priority": "low",
        "track": ["releases"],
        "paths_of_interest": [],
    },

    # ── Observability ─────────────────────────────────────────────────────
    "open-telemetry/opentelemetry-python": {
        "purpose": "Tracing and observability SDK",
        "category": "observability",
        "priority": "low",
        "track": ["releases"],
        "paths_of_interest": [],
    },

    # ── GitHub Actions ────────────────────────────────────────────────────
    "actions/checkout": {
        "purpose": "CI/CD — used in all SLATE workflows",
        "category": "ci",
        "priority": "medium",
        "track": ["releases", "tags"],
        "paths_of_interest": [],
    },
    "actions/upload-artifact": {
        "purpose": "CI/CD — artifact storage",
        "category": "ci",
        "priority": "low",
        "track": ["releases"],
        "paths_of_interest": [],
    },

    # ── Claude / Anthropic ─────────────────────────────────────────────────
    "anthropics/claude-code": {
        "purpose": "Claude Code CLI — skills format, slash commands",
        "category": "claude",
        "priority": "critical",
        "track": ["releases", "tags"],
        "paths_of_interest": [
            "src/",
            "skills/",
        ],
    },
    "anthropics/anthropic-sdk-python": {
        "purpose": "Anthropic Python SDK — API integration",
        "category": "claude",
        "priority": "high",
        "track": ["releases"],
        "paths_of_interest": [
            "src/anthropic/",
        ],
    },

    # ── GitHub Tools ────────────────────────────────────────────────────────
    "actions/runner": {
        "purpose": "GitHub Actions self-hosted runner",
        "category": "github",
        "priority": "high",
        "track": ["releases"],
        "paths_of_interest": [
            "src/Runner.Worker/",
            "src/Runner.Listener/",
        ],
    },
    "cli/cli": {
        "purpose": "GitHub CLI (gh) — API and workflow management",
        "category": "github",
        "priority": "medium",
        "track": ["releases"],
        "paths_of_interest": [
            "pkg/cmd/",
            "api/",
        ],
    },

    # ── Additional AI ───────────────────────────────────────────────────────
    "huggingface/peft": {
        "purpose": "Parameter-Efficient Fine-Tuning — LoRA adapters",
        "category": "ai",
        "priority": "low",
        "track": ["releases"],
        "paths_of_interest": [],
    },

    # ── Development Tools ──────────────────────────────────────────────────
    "github/spec-kit": {
        "purpose": "Spec-Driven Development toolkit — specification format",
        "category": "dev",
        "priority": "medium",
        "track": ["releases", "tags"],
        "paths_of_interest": [
            "src/",
            "lib/",
        ],
    },
}


def _get_token() -> str:
    """Get GitHub token from git credential manager."""
    try:
        result = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n",
            capture_output=True, text=True, timeout=15,
        )
        for line in result.stdout.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1]
    except Exception:
        pass
    return ""


def _api_request(path: str, method: str = "GET",
                 data: Optional[dict] = None, token: str = "") -> dict:
    """Make GitHub API request."""
    url = f"{API_BASE}{path}" if path.startswith("/") else path
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "SLATE-DependencyForkManager/2.4.0",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    if body:
        req.add_header("Content-Type", "application/json")

    try:
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
        with opener.open(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        return {"error": True, "status": e.code, "message": error_body}
    except Exception as e:
        return {"error": True, "message": str(e)}


def check_fork_exists(upstream: str, token: str) -> dict:
    """Check if we already have a fork of the upstream repo."""
    owner, repo = upstream.split("/")
    # Check if the repo exists in our org
    result = _api_request(f"/repos/{ORG}/{repo}", token=token)
    if result.get("error"):
        return {"exists": False, "upstream": upstream}

    # Verify it's actually a fork of the right repo
    is_fork = result.get("fork", False)
    parent = result.get("parent", {}).get("full_name", "")

    return {
        "exists": True,
        "is_fork": is_fork,
        "parent": parent,
        "correct_parent": parent == upstream,
        "full_name": result.get("full_name", ""),
        "default_branch": result.get("default_branch", "main"),
        "updated_at": result.get("updated_at", ""),
        "html_url": result.get("html_url", ""),
    }


def get_upstream_info(upstream: str, token: str) -> dict:
    """Get latest release and commit info from upstream."""
    info = {
        "upstream": upstream,
        "latest_release": None,
        "latest_release_date": None,
        "default_branch": "main",
        "latest_commit": None,
        "latest_commit_date": None,
    }

    # Get repo info
    repo_data = _api_request(f"/repos/{upstream}", token=token)
    if not repo_data.get("error"):
        info["default_branch"] = repo_data.get("default_branch", "main")

    # Get latest release
    releases = _api_request(f"/repos/{upstream}/releases?per_page=1", token=token)
    if isinstance(releases, list) and releases:
        info["latest_release"] = releases[0].get("tag_name", "")
        info["latest_release_date"] = releases[0].get("published_at", "")

    # Get latest commit on default branch
    branch = info["default_branch"]
    commits = _api_request(
        f"/repos/{upstream}/commits?sha={branch}&per_page=1", token=token
    )
    if isinstance(commits, list) and commits:
        info["latest_commit"] = commits[0].get("sha", "")[:12]
        info["latest_commit_date"] = (
            commits[0].get("commit", {}).get("committer", {}).get("date", "")
        )

    return info


def get_fork_drift(upstream: str, fork_repo: str, token: str) -> dict:
    """Compare fork with upstream to measure drift."""
    owner, repo = upstream.split("/")
    fork_owner = fork_repo.split("/")[0]

    # Use compare API
    default_branch = "main"
    repo_data = _api_request(f"/repos/{upstream}", token=token)
    if not repo_data.get("error"):
        default_branch = repo_data.get("default_branch", "main")

    compare = _api_request(
        f"/repos/{upstream}/compare/{default_branch}...{fork_owner}:{default_branch}",
        token=token,
    )

    if compare.get("error"):
        return {"error": True, "message": compare.get("message", "Compare failed")}

    return {
        "status": compare.get("status", "unknown"),
        "ahead_by": compare.get("ahead_by", 0),
        "behind_by": compare.get("behind_by", 0),
        "total_commits": compare.get("total_commits", 0),
    }


def fork_repo(upstream: str, token: str) -> dict:
    """Fork an upstream repo into the SLATE account."""
    # Modified: 2026-02-07T23:15:00Z | Author: COPILOT | Change: Handle user account vs org forking
    print(f"  Forking {upstream} → {ORG}/...")

    # First try as organization fork
    result = _api_request(
        f"/repos/{upstream}/forks",
        method="POST",
        data={"organization": ORG, "default_branch_only": True},
        token=token,
    )

    # If org fork fails (user account), retry without organization param
    if result.get("error") and result.get("status") == 422:
        result = _api_request(
            f"/repos/{upstream}/forks",
            method="POST",
            data={"default_branch_only": True},
            token=token,
        )

    if result.get("error"):
        return {
            "success": False,
            "error": result.get("message", "Fork failed"),
            "status": result.get("status", 0),
        }

    return {
        "success": True,
        "full_name": result.get("full_name", ""),
        "html_url": result.get("html_url", ""),
        "default_branch": result.get("default_branch", "main"),
    }


def sync_fork(upstream: str, token: str) -> dict:
    """Sync a fork with its upstream (GitHub's merge-upstream API)."""
    owner, repo = upstream.split("/")
    fork_full = f"{ORG}/{repo}"

    # Get default branch
    repo_data = _api_request(f"/repos/{upstream}", token=token)
    default_branch = "main"
    if not repo_data.get("error"):
        default_branch = repo_data.get("default_branch", "main")

    # Use GitHub's merge-upstream endpoint
    result = _api_request(
        f"/repos/{fork_full}/merge-upstream",
        method="POST",
        data={"branch": default_branch},
        token=token,
    )

    if result.get("error"):
        return {
            "success": False,
            "error": result.get("message", "Sync failed"),
            "upstream": upstream,
        }

    return {
        "success": True,
        "message": result.get("message", "Synced"),
        "merge_type": result.get("merge_type", ""),
        "upstream": upstream,
        "fork": fork_full,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Commands
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_status(token: str, as_json: bool = False) -> int:
    """Show status of all dependency forks."""
    results = []

    for upstream, meta in DEPENDENCY_FORKS.items():
        owner, repo = upstream.split("/")
        fork_info = check_fork_exists(upstream, token)
        upstream_info = get_upstream_info(upstream, token)

        entry = {
            "upstream": upstream,
            "purpose": meta["purpose"],
            "category": meta["category"],
            "priority": meta["priority"],
            "fork_exists": fork_info["exists"],
            "latest_release": upstream_info.get("latest_release", ""),
            "latest_commit": upstream_info.get("latest_commit", ""),
            "latest_commit_date": upstream_info.get("latest_commit_date", ""),
        }

        if fork_info["exists"]:
            entry["fork_url"] = fork_info.get("html_url", "")
            entry["correct_parent"] = fork_info.get("correct_parent", False)
            entry["fork_updated"] = fork_info.get("updated_at", "")

        results.append(entry)

    if as_json:
        print(json.dumps(results, indent=2))
        return 0

    # Table output
    print("═" * 90)
    print("  SLATE Dependency Fork Status")
    print("═" * 90)
    print()

    for cat in ["core", "web", "ai", "observability", "ci", "claude", "github", "dev"]:
        cat_items = [r for r in results if r["category"] == cat]
        if not cat_items:
            continue
        print(f"  ── {cat.upper()} ──")
        for r in cat_items:
            status = "✓ FORKED" if r["fork_exists"] else "✗ NOT FORKED"
            release = r.get("latest_release", "—") or "—"
            pri = r["priority"].upper()
            print(f"    [{pri:6s}] {status:14s}  {r['upstream']:<40s}  latest: {release}")
        print()

    forked = sum(1 for r in results if r["fork_exists"])
    total = len(results)
    print(f"  Summary: {forked}/{total} dependencies forked")
    print()
    return 0


def cmd_check(token: str, as_json: bool = False) -> int:
    """Check upstream drift for all existing forks."""
    results = []

    for upstream, meta in DEPENDENCY_FORKS.items():
        fork_info = check_fork_exists(upstream, token)
        if not fork_info["exists"]:
            continue

        drift = get_fork_drift(upstream, fork_info["full_name"], token)
        entry = {
            "upstream": upstream,
            "fork": fork_info["full_name"],
            "behind_by": drift.get("behind_by", 0),
            "ahead_by": drift.get("ahead_by", 0),
            "status": drift.get("status", "unknown"),
            "priority": meta["priority"],
        }
        results.append(entry)

    if as_json:
        print(json.dumps(results, indent=2))
        return 0

    print("═" * 80)
    print("  SLATE Dependency Fork Drift Report")
    print("═" * 80)
    print()
    print(f"  {'Upstream':<40s}  {'Behind':>7s}  {'Ahead':>6s}  Status")
    print(f"  {'-'*40}  {'-'*7}  {'-'*6}  {'-'*12}")

    needs_sync = 0
    for r in results:
        behind = r["behind_by"]
        status_icon = "✓ current" if behind == 0 else f"⚠ {behind} behind"
        if behind > 0:
            needs_sync += 1
        print(f"  {r['upstream']:<40s}  {behind:>7d}  {r['ahead_by']:>6d}  {status_icon}")

    print()
    if needs_sync > 0:
        print(f"  ⚠ {needs_sync} fork(s) need syncing. Run: --sync-all")
    else:
        print("  ✓ All forks are current with upstream")
    print()
    return 0


def cmd_fork(upstream: str, token: str) -> int:
    """Fork a single upstream repo."""
    print(f"Forking {upstream} into {ORG}...")

    # Check if already forked
    fork_info = check_fork_exists(upstream, token)
    if fork_info["exists"]:
        print(f"  ✓ Already forked: {fork_info.get('html_url', '')}")
        return 0

    result = fork_repo(upstream, token)
    if result["success"]:
        print(f"  ✓ Forked: {result['html_url']}")
        return 0
    else:
        print(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
        return 1


def cmd_sync(upstream: str, token: str) -> int:
    """Sync a single fork with upstream."""
    print(f"Syncing {ORG}/{upstream.split('/')[-1]} with {upstream}...")

    result = sync_fork(upstream, token)
    if result["success"]:
        print(f"  ✓ {result.get('message', 'Synced')}")
        return 0
    else:
        print(f"  ✗ {result.get('error', 'Sync failed')}")
        return 1


def cmd_sync_all(token: str) -> int:
    """Sync all existing forks."""
    print("═" * 60)
    print("  Syncing all dependency forks with upstream")
    print("═" * 60)
    print()

    synced = 0
    failed = 0
    skipped = 0

    for upstream in DEPENDENCY_FORKS:
        fork_info = check_fork_exists(upstream, token)
        if not fork_info["exists"]:
            print(f"  SKIP  {upstream} (not forked)")
            skipped += 1
            continue

        result = sync_fork(upstream, token)
        if result["success"]:
            msg = result.get("message", "synced")
            print(f"  ✓     {upstream} — {msg}")
            synced += 1
        else:
            print(f"  ✗     {upstream} — {result.get('error', 'failed')}")
            failed += 1

    print()
    print(f"  Results: {synced} synced, {failed} failed, {skipped} skipped")
    return 0 if failed == 0 else 1


def cmd_init(token: str) -> int:
    """Fork all tracked dependencies that aren't forked yet."""
    print("═" * 60)
    print("  Initializing all SLATE dependency forks")
    print("═" * 60)
    print()

    created = 0
    existed = 0
    failed = 0

    for upstream, meta in DEPENDENCY_FORKS.items():
        fork_info = check_fork_exists(upstream, token)
        if fork_info["exists"]:
            print(f"  EXISTS  {upstream}")
            existed += 1
            continue

        result = fork_repo(upstream, token)
        if result["success"]:
            print(f"  ✓ FORK  {upstream} → {result.get('full_name', '')}")
            created += 1
        else:
            print(f"  ✗ FAIL  {upstream} — {result.get('error', '')[:80]}")
            failed += 1

    print()
    print(f"  Results: {created} created, {existed} already existed, {failed} failed")
    return 0 if failed == 0 else 1


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(
        description="SLATE Dependency Fork Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --status                     Show all fork statuses
  %(prog)s --check                      Check upstream drift
  %(prog)s --fork microsoft/vscode      Fork a specific repo
  %(prog)s --sync ollama/ollama         Sync a specific fork
  %(prog)s --sync-all                   Sync all forks with upstream
  %(prog)s --init                       Fork all tracked dependencies
""",
    )
    parser.add_argument("--status", action="store_true", help="Show all fork statuses")
    parser.add_argument("--check", action="store_true", help="Check upstream drift")
    parser.add_argument("--fork", type=str, metavar="OWNER/REPO",
                        help="Fork a specific upstream repo")
    parser.add_argument("--sync", type=str, metavar="OWNER/REPO",
                        help="Sync a specific fork with upstream")
    parser.add_argument("--sync-all", action="store_true", help="Sync all forks")
    parser.add_argument("--init", action="store_true",
                        help="Fork all tracked dependencies")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--add", type=str, metavar="OWNER/REPO",
                        help="Add a new dependency to track (use with --purpose)")
    parser.add_argument("--purpose", type=str, default="",
                        help="Purpose description (used with --add)")

    args = parser.parse_args()

    token = _get_token()
    if not token:
        print("Error: Could not get GitHub token from git credential manager")
        print("Run: git credential fill  (with protocol=https, host=github.com)")
        return 1

    if args.status:
        return cmd_status(token, as_json=args.json)
    elif args.check:
        return cmd_check(token, as_json=args.json)
    elif args.fork:
        return cmd_fork(args.fork, token)
    elif args.sync:
        return cmd_sync(args.sync, token)
    elif args.sync_all:
        return cmd_sync_all(token)
    elif args.init:
        return cmd_init(token)
    else:
        # Default: show status
        return cmd_status(token, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
