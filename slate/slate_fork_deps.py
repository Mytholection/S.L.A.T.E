#!/usr/bin/env python3
# Modified: 2026-02-07T07:00:00Z | Author: Claude | Change: Fork dependency manager
"""
SLATE Fork Dependencies Manager
================================
Manages forked dependencies for vendor lock-in protection.

Usage:
    python slate/slate_fork_deps.py --status
    python slate/slate_fork_deps.py --sync
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

FORKED_DEPS = {
    "claude-code": {
        "upstream": "anthropics/claude-code",
        "fork": "SynchronizedLivingArchitecture/claude-code",
        "branch": "main",
        "category": "claude",
    },
    "anthropic-sdk-python": {
        "upstream": "anthropics/anthropic-sdk-python",
        "fork": "SynchronizedLivingArchitecture/anthropic-sdk-python",
        "branch": "main",
        "category": "claude",
        "pip_name": "anthropic",
    },
    "transformers": {
        "upstream": "huggingface/transformers",
        "fork": "SynchronizedLivingArchitecture/transformers",
        "branch": "main",
        "category": "ai",
        "pip_name": "transformers",
    },
    "accelerate": {
        "upstream": "huggingface/accelerate",
        "fork": "SynchronizedLivingArchitecture/accelerate",
        "branch": "main",
        "category": "ai",
        "pip_name": "accelerate",
    },
    "peft": {
        "upstream": "huggingface/peft",
        "fork": "SynchronizedLivingArchitecture/peft",
        "branch": "main",
        "category": "ai",
        "pip_name": "peft",
    },
    "chroma": {
        "upstream": "chroma-core/chroma",
        "fork": "SynchronizedLivingArchitecture/chroma",
        "branch": "main",
        "category": "database",
        "pip_name": "chromadb",
    },
    "runner": {
        "upstream": "actions/runner",
        "fork": "SynchronizedLivingArchitecture/runner",
        "branch": "main",
        "category": "github",
    },
    "cli": {
        "upstream": "cli/cli",
        "fork": "SynchronizedLivingArchitecture/cli",
        "branch": "trunk",
        "category": "github",
    },
}


class SlateForkManager:
    """Manages SLATE's forked dependencies."""

    def __init__(self):
        self.workspace = WORKSPACE_ROOT
        self.gh_cli = self._find_gh_cli()

    def _find_gh_cli(self) -> str:
        local_gh = self.workspace / ".tools" / "gh.exe"
        if local_gh.exists():
            return str(local_gh)
        return "gh"

    def _run_gh(self, args, timeout=30):
        cmd = [self.gh_cli] + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              cwd=str(self.workspace))

    def check_auth(self) -> bool:
        result = self._run_gh(["auth", "status"])
        return result.returncode == 0

    def get_fork_status(self, name: str) -> dict:
        if name not in FORKED_DEPS:
            return {"name": name, "exists": False, "error": f"Unknown: {name}"}

        dep = FORKED_DEPS[name]
        status = {"name": name, "upstream": dep["upstream"], "fork": dep["fork"], "exists": False}

        try:
            result = self._run_gh(["repo", "view", dep["fork"], "--json", "updatedAt"])
            if result.returncode == 0:
                data = json.loads(result.stdout)
                status["exists"] = True
                status["last_sync"] = data.get("updatedAt")
            else:
                status["error"] = "Fork not found"
        except Exception as e:
            status["error"] = str(e)

        return status

    def get_all_status(self) -> dict:
        return {name: self.get_fork_status(name) for name in FORKED_DEPS}

    def sync_fork(self, name: str) -> bool:
        if name not in FORKED_DEPS:
            return False

        dep = FORKED_DEPS[name]
        print(f"  Syncing {name} from {dep['upstream']}...")

        result = self._run_gh([
            "api", "--method", "POST",
            "-H", "Accept: application/vnd.github+json",
            f"/repos/{dep['fork']}/merge-upstream",
            "-f", f"branch={dep['branch']}"
        ], timeout=60)

        if result.returncode == 0 or "already" in result.stderr.lower():
            print(f"  [OK] {name} synced")
            return True
        print(f"  [!] {name} failed: {result.stderr}")
        return False

    def sync_all(self) -> dict:
        return {name: self.sync_fork(name) for name in FORKED_DEPS}

    def print_status(self):
        print()
        print("=" * 60)
        print("  SLATE Forked Dependencies")
        print("=" * 60)
        print()

        if not self.check_auth():
            print("  [!] GitHub CLI not authenticated")
            return

        for name, dep in FORKED_DEPS.items():
            status = self.get_fork_status(name)
            icon = "✓" if status.get("exists") else "✗"
            print(f"  {icon} {name}: {dep['fork']}")

        print()
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="SLATE Fork Manager")
    parser.add_argument("--status", action="store_true", help="Show fork status")
    parser.add_argument("--sync", action="store_true", help="Sync all forks")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--list", action="store_true", help="List forks")

    args = parser.parse_args()
    manager = SlateForkManager()

    if args.list:
        for name, dep in FORKED_DEPS.items():
            print(f"{name}: {dep['upstream']} -> {dep['fork']}")
    elif args.sync:
        manager.sync_all()
    elif args.json:
        print(json.dumps(manager.get_all_status(), indent=2, default=str))
    else:
        manager.print_status()


if __name__ == "__main__":
    main()
