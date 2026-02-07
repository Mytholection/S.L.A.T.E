#!/usr/bin/env python3
"""
SLATE Discussion Manager

Manages GitHub Discussions integration with the SLATE workflow system.
Tracks engagement, routes discussions to appropriate boards, and syncs
actionable items to the task queue.

Usage:
    python slate/slate_discussion_manager.py --status
    python slate/slate_discussion_manager.py --unanswered
    python slate/slate_discussion_manager.py --sync-tasks
    python slate/slate_discussion_manager.py --metrics
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add workspace root to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

try:
    import filelock
except ImportError:
    filelock = None  # Graceful degradation

# Constants
REPO_OWNER = "SynchronizedLivingArchitecture"
REPO_NAME = "S.L.A.T.E"
DISCUSSION_LOG_FILE = WORKSPACE_ROOT / ".slate_discussions" / "discussion_log.json"
METRICS_FILE = WORKSPACE_ROOT / ".slate_discussions" / "metrics.json"


def _find_gh_cli() -> str:
    """Find gh CLI path, checking .tools first."""
    gh_path = WORKSPACE_ROOT / ".tools" / "gh.exe"
    if gh_path.exists():
        return str(gh_path)
    return "gh"  # Fall back to PATH


def run_gh_command(args: list[str]) -> tuple[bool, str]:
    """Run a gh CLI command and return success status and output."""
    gh_cli = _find_gh_cli()
    try:
        result = subprocess.run(
            [gh_cli] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return result.returncode == 0, result.stdout or result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except FileNotFoundError:
        return False, "gh CLI not found"


def run_graphql_query(query: str, variables: dict[str, Any] | None = None) -> tuple[bool, dict[str, Any]]:
    """Run a GraphQL query via gh CLI."""
    args = ["api", "graphql", "-f", f"query={query}"]
    if variables:
        for key, value in variables.items():
            args.extend(["-f", f"{key}={value}"])

    success, output = run_gh_command(args)
    if success:
        try:
            return True, json.loads(output)
        except json.JSONDecodeError:
            return False, {"error": "Invalid JSON response"}
    return False, {"error": output}


def ensure_log_directory() -> None:
    """Ensure the discussion log directory exists."""
    DISCUSSION_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def _get_lock(path: Path) -> Any:
    """Get a file lock, with graceful fallback if filelock not available."""
    if filelock is not None:
        return filelock.FileLock(str(path) + ".lock", timeout=10)
    # Fallback: return a no-op context manager
    from contextlib import nullcontext
    return nullcontext()


def load_discussion_log() -> dict[str, Any]:
    """Load the discussion log from disk."""
    ensure_log_directory()
    if DISCUSSION_LOG_FILE.exists():
        try:
            with _get_lock(DISCUSSION_LOG_FILE):
                return json.loads(DISCUSSION_LOG_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"events": [], "discussions": {}}


def save_discussion_log(log: dict[str, Any]) -> None:
    """Save the discussion log to disk."""
    ensure_log_directory()
    with _get_lock(DISCUSSION_LOG_FILE):
        DISCUSSION_LOG_FILE.write_text(json.dumps(log, indent=2))


def log_event(
    event: str,
    discussion: str,
    title: str = "",
    category: str = "",
    author: str = "",
) -> None:
    """Log a discussion event."""
    log = load_discussion_log()

    event_data = {
        "timestamp": datetime.now().isoformat(),
        "event": event,
        "discussion": discussion,
        "title": title,
        "category": category,
        "author": author,
    }
    log["events"].append(event_data)

    # Keep only last 1000 events
    if len(log["events"]) > 1000:
        log["events"] = log["events"][-1000:]

    # Track discussion metadata
    if discussion not in log["discussions"]:
        log["discussions"][discussion] = {
            "first_seen": datetime.now().isoformat(),
            "title": title,
            "category": category,
            "events": [],
        }
    log["discussions"][discussion]["events"].append(event)
    log["discussions"][discussion]["last_updated"] = datetime.now().isoformat()

    save_discussion_log(log)
    print(f"Logged: {event} for discussion #{discussion}")


def track_qa(discussion: str) -> None:
    """Track a Q&A discussion for response metrics."""
    log = load_discussion_log()

    if "qa_tracking" not in log:
        log["qa_tracking"] = {}

    if discussion not in log["qa_tracking"]:
        log["qa_tracking"][discussion] = {
            "created_at": datetime.now().isoformat(),
            "answered": False,
            "response_time": None,
        }

    save_discussion_log(log)
    print(f"Tracking Q&A discussion #{discussion}")


def get_discussions(category_filter: str = "") -> list[dict[str, Any]]:
    """Fetch discussions from GitHub."""
    query = """
    query($owner: String!, $repo: String!) {
      repository(owner: $owner, name: $repo) {
        discussions(first: 100, orderBy: {field: CREATED_AT, direction: DESC}) {
          nodes {
            number
            title
            body
            category { name emoji isAnswerable }
            author { login }
            createdAt
            updatedAt
            isAnswered
            comments { totalCount }
            labels(first: 10) { nodes { name } }
          }
          pageInfo { hasNextPage endCursor }
        }
      }
    }
    """

    success, result = run_graphql_query(query, {"owner": REPO_OWNER, "repo": REPO_NAME})
    if not success:
        print(f"Error fetching discussions: {result.get('error', 'Unknown error')}")
        return []

    try:
        discussions = result["data"]["repository"]["discussions"]["nodes"]
        if category_filter:
            discussions = [
                d for d in discussions
                if d["category"]["name"].lower() == category_filter.lower()
            ]
        return discussions
    except (KeyError, TypeError):
        return []


def get_discussion_categories() -> list[dict[str, Any]]:
    """Fetch discussion categories from GitHub."""
    query = """
    query($owner: String!, $repo: String!) {
      repository(owner: $owner, name: $repo) {
        discussionCategories(first: 20) {
          nodes {
            id
            name
            emoji
            description
            isAnswerable
          }
        }
      }
    }
    """

    success, result = run_graphql_query(query, {"owner": REPO_OWNER, "repo": REPO_NAME})
    if not success:
        return []

    try:
        return result["data"]["repository"]["discussionCategories"]["nodes"]
    except (KeyError, TypeError):
        return []


def get_unanswered_discussions() -> list[dict[str, Any]]:
    """Get unanswered Q&A discussions."""
    discussions = get_discussions()
    unanswered = [
        d for d in discussions
        if d.get("category", {}).get("isAnswerable", False)
        and not d.get("isAnswered", False)
    ]
    return unanswered


def check_stale_discussions(days: int = 7) -> list[dict[str, Any]]:
    """Check for stale unanswered discussions."""
    unanswered = get_unanswered_discussions()
    cutoff = datetime.now() - timedelta(days=days)

    stale = []
    for d in unanswered:
        try:
            created = datetime.fromisoformat(d["createdAt"].replace("Z", "+00:00"))
            if created.replace(tzinfo=None) < cutoff:
                stale.append(d)
        except (ValueError, KeyError):
            continue

    return stale


def generate_metrics() -> dict[str, Any]:
    """Generate engagement metrics for discussions."""
    discussions = get_discussions()
    categories = get_discussion_categories()

    metrics = {
        "generated_at": datetime.now().isoformat(),
        "total_discussions": len(discussions),
        "by_category": {},
        "engagement": {
            "total_comments": 0,
            "answered": 0,
            "unanswered": 0,
        },
        "recent_activity": {
            "last_24h": 0,
            "last_7d": 0,
            "last_30d": 0,
        },
    }

    # Count by category
    for cat in categories:
        metrics["by_category"][cat["name"]] = 0

    now = datetime.now()
    for d in discussions:
        # Category count
        cat_name = d.get("category", {}).get("name", "Unknown")
        if cat_name in metrics["by_category"]:
            metrics["by_category"][cat_name] += 1
        else:
            metrics["by_category"][cat_name] = 1

        # Engagement
        metrics["engagement"]["total_comments"] += d.get("comments", {}).get("totalCount", 0)
        if d.get("isAnswered"):
            metrics["engagement"]["answered"] += 1
        else:
            metrics["engagement"]["unanswered"] += 1

        # Recent activity
        try:
            updated = datetime.fromisoformat(d["updatedAt"].replace("Z", "+00:00"))
            updated = updated.replace(tzinfo=None)
            age = now - updated
            if age < timedelta(days=1):
                metrics["recent_activity"]["last_24h"] += 1
            if age < timedelta(days=7):
                metrics["recent_activity"]["last_7d"] += 1
            if age < timedelta(days=30):
                metrics["recent_activity"]["last_30d"] += 1
        except (ValueError, KeyError):
            continue

    # Save metrics
    ensure_log_directory()
    METRICS_FILE.write_text(json.dumps(metrics, indent=2))

    return metrics


def sync_to_tasks() -> int:
    """Sync actionable discussions to the task queue."""
    tasks_file = WORKSPACE_ROOT / "current_tasks.json"

    # Load current tasks
    if tasks_file.exists():
        try:
            with _get_lock(tasks_file):
                data = json.loads(tasks_file.read_text())
                tasks = data.get("tasks", []) if isinstance(data, dict) else data
        except (json.JSONDecodeError, OSError):
            tasks = []
    else:
        tasks = []

    # Get existing discussion task IDs
    existing_ids = {t.get("id", "") for t in tasks if "discussion" in t.get("id", "")}

    # Find actionable discussions (Ideas, Feature requests, Bug reports)
    discussions = get_discussions()
    actionable_categories = {"ideas", "feature", "bugs", "issues"}

    added = 0
    for d in discussions:
        cat_name = d.get("category", {}).get("name", "").lower()
        if any(ac in cat_name for ac in actionable_categories):
            task_id = f"discussion-{d['number']}"
            if task_id not in existing_ids:
                task = {
                    "id": task_id,
                    "title": f"[Discussion #{d['number']}] {d['title']}",
                    "status": "pending",
                    "priority": "normal",
                    "source": "github_discussion",
                    "category": d.get("category", {}).get("name", ""),
                    "author": d.get("author", {}).get("login", "unknown"),
                    "created_at": d.get("createdAt", ""),
                    "assigned_to": "workflow",
                }
                tasks.append(task)
                added += 1
                print(f"Added task: {task_id} - {d['title']}")

    if added > 0:
        with _get_lock(tasks_file):
            tasks_file.write_text(json.dumps({"tasks": tasks}, indent=2))
        print(f"Synced {added} discussions to task queue")
    else:
        print("No new actionable discussions found")

    return added


def show_status() -> None:
    """Show discussion system status."""
    print("=" * 50)
    print("SLATE Discussion Manager Status")
    print("=" * 50)

    # Check gh CLI
    success, output = run_gh_command(["auth", "status"])
    print(f"\nGitHub CLI: {'OK' if success else 'Not authenticated'}")

    # Get categories
    categories = get_discussion_categories()
    print(f"\nDiscussion Categories: {len(categories)}")
    for cat in categories:
        emoji = cat.get("emoji", "")
        name = cat.get("name", "")
        answerable = "[Q&A]" if cat.get("isAnswerable") else ""
        print(f"  {emoji} {name} {answerable}")

    # Get discussions summary
    discussions = get_discussions()
    print(f"\nTotal Discussions: {len(discussions)}")

    unanswered = get_unanswered_discussions()
    print(f"Unanswered Q&A: {len(unanswered)}")

    stale = check_stale_discussions()
    print(f"Stale (>7 days): {len(stale)}")

    # Check log file
    log = load_discussion_log()
    print(f"\nLogged Events: {len(log.get('events', []))}")
    print(f"Tracked Discussions: {len(log.get('discussions', {}))}")


def process_all() -> None:
    """Process all discussions - full sync and cleanup."""
    print("Processing all discussions...")

    # Generate metrics
    print("\n--- Generating Metrics ---")
    metrics = generate_metrics()
    print(f"Total: {metrics['total_discussions']}")
    print(f"Comments: {metrics['engagement']['total_comments']}")
    print(f"Answered: {metrics['engagement']['answered']}")
    print(f"Unanswered: {metrics['engagement']['unanswered']}")

    # Check stale
    print("\n--- Checking Stale Discussions ---")
    stale = check_stale_discussions()
    for d in stale:
        print(f"  STALE: #{d['number']} - {d['title']}")

    # Sync to tasks
    print("\n--- Syncing to Tasks ---")
    sync_to_tasks()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="SLATE Discussion Manager")

    parser.add_argument("--status", action="store_true", help="Show discussion system status")
    parser.add_argument("--unanswered", action="store_true", help="List unanswered Q&A discussions")
    parser.add_argument("--check-stale", action="store_true", help="Check for stale discussions")
    parser.add_argument("--sync-tasks", action="store_true", help="Sync actionable discussions to task queue")
    parser.add_argument("--metrics", action="store_true", help="Generate engagement metrics")
    parser.add_argument("--process-all", action="store_true", help="Full processing run")
    parser.add_argument("--categories", action="store_true", help="List discussion categories")

    # Event logging
    parser.add_argument("--log", action="store_true", help="Log an event")
    parser.add_argument("--event", type=str, help="Event type to log")
    parser.add_argument("--discussion", type=str, help="Discussion number")
    parser.add_argument("--title", type=str, default="", help="Discussion title")
    parser.add_argument("--category", type=str, default="", help="Discussion category")
    parser.add_argument("--author", type=str, default="", help="Author")

    # Q&A tracking
    parser.add_argument("--track-qa", action="store_true", help="Track Q&A discussion")

    # Output format
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Handle commands
    if args.log and args.event and args.discussion:
        log_event(args.event, args.discussion, args.title, args.category, args.author)
        return 0

    if args.track_qa and args.discussion:
        track_qa(args.discussion)
        return 0

    if args.status:
        show_status()
        return 0

    if args.unanswered:
        unanswered = get_unanswered_discussions()
        if args.json:
            print(json.dumps(unanswered, indent=2))
        else:
            print(f"Unanswered Q&A Discussions: {len(unanswered)}")
            for d in unanswered:
                print(f"  #{d['number']}: {d['title']}")
                print(f"    Author: {d.get('author', {}).get('login', 'unknown')}")
                print(f"    Comments: {d.get('comments', {}).get('totalCount', 0)}")
        return 0

    if args.check_stale:
        stale = check_stale_discussions()
        if args.json:
            print(json.dumps(stale, indent=2))
        else:
            print(f"Stale Discussions (>7 days): {len(stale)}")
            for d in stale:
                print(f"  #{d['number']}: {d['title']}")
        return 0

    if args.sync_tasks:
        sync_to_tasks()
        return 0

    if args.metrics:
        metrics = generate_metrics()
        if args.json:
            print(json.dumps(metrics, indent=2))
        else:
            print("Discussion Metrics")
            print(f"  Total: {metrics['total_discussions']}")
            print("  By Category:")
            for cat, count in metrics["by_category"].items():
                print(f"    {cat}: {count}")
            print("  Engagement:")
            print(f"    Total Comments: {metrics['engagement']['total_comments']}")
            print(f"    Answered: {metrics['engagement']['answered']}")
            print(f"    Unanswered: {metrics['engagement']['unanswered']}")
        return 0

    if args.process_all:
        process_all()
        return 0

    if args.categories:
        categories = get_discussion_categories()
        if args.json:
            print(json.dumps(categories, indent=2))
        else:
            print("Discussion Categories:")
            for cat in categories:
                emoji = cat.get("emoji", "")
                name = cat.get("name", "")
                desc = cat.get("description", "")
                print(f"  {emoji} {name}")
                if desc:
                    print(f"    {desc}")
        return 0

    # Default: show status
    show_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
