#!/usr/bin/env python3
"""
SLATE Model Trainer — Build & Manage Custom SLATE Models
=========================================================
# Modified: 2026-02-07T06:00:00Z | Author: COPILOT | Change: Initial SLATE model trainer

Builds custom Ollama models for the SLATE agentic system using Modelfiles.
Manages model lifecycle: build, test, benchmark, and deploy across dual GPUs.

Models:
- slate-coder: 12B code generation model (mistral-nemo base, GPU 0)
- slate-fast: 3B quick classification/summary model (llama3.2 base, GPU 1)
- slate-planner: 7B planning/analysis model (mistral base, GPU 0/1)

Usage:
    python slate/slate_model_trainer.py --build-all          # Build all SLATE models
    python slate/slate_model_trainer.py --build slate-coder  # Build specific model
    python slate/slate_model_trainer.py --test               # Test all models
    python slate/slate_model_trainer.py --status             # Model status
    python slate/slate_model_trainer.py --benchmark          # Benchmark SLATE models
    python slate/slate_model_trainer.py --update-context     # Update models with latest codebase
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# Modified: 2026-02-07T06:00:00Z | Author: COPILOT | Change: workspace setup
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

OLLAMA_BASE = "http://127.0.0.1:11434"
MODELS_DIR = WORKSPACE_ROOT / "models"
STATE_FILE = WORKSPACE_ROOT / ".slate_model_state.json"
LOG_DIR = WORKSPACE_ROOT / "slate_logs" / "models"

# SLATE model definitions
SLATE_MODELS = {
    "slate-coder": {
        "modelfile": "Modelfile.slate-coder",
        "base": "mistral-nemo:latest",
        "purpose": "Code generation, review, and architecture",
        "gpu": 0,
        "priority": 1,
        "test_prompt": "Write a Python function that checks if Ollama is running on 127.0.0.1:11434",
        "expected_keywords": ["urllib", "127.0.0.1", "11434", "def"],
    },
    "slate-fast": {
        "modelfile": "Modelfile.slate-fast",
        "base": "llama3.2:3b",
        "purpose": "Task classification, quick summaries",
        "gpu": 1,
        "priority": 2,
        "test_prompt": "Classify this task: Add unit tests for the runner manager module",
        "expected_keywords": ["test"],
    },
    "slate-planner": {
        "modelfile": "Modelfile.slate-planner",
        "base": "mistral:latest",
        "purpose": "Architecture analysis, planning",
        "gpu": 0,
        "priority": 3,
        "test_prompt": "Break down this task: Implement dual-GPU load balancing for model inference",
        "expected_keywords": ["gpu", "model", "load"],
    },
}


class SlateModelTrainer:
    """Builds and manages custom SLATE Ollama models."""

    # Modified: 2026-02-07T06:00:00Z | Author: COPILOT | Change: model trainer core

    def __init__(self):
        self.workspace = WORKSPACE_ROOT
        self.models_dir = MODELS_DIR
        self.state = self._load_state()
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> dict:
        """Load trainer state."""
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "models_built": {},
            "last_build": None,
            "last_test": None,
            "build_history": [],
            "test_results": {},
        }

    def _save_state(self):
        """Save trainer state."""
        STATE_FILE.write_text(json.dumps(self.state, indent=2, default=str), encoding="utf-8")

    def _log(self, msg: str, level: str = "INFO"):
        """Log a message."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"[{ts}] [TRAINER] [{level}] {msg}"
        print(line)
        log_file = LOG_DIR / f"trainer_{datetime.now().strftime('%Y%m%d')}.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _ollama_request(self, path: str, data: dict | None = None,
                        timeout: int = 120) -> dict:
        """Make a request to Ollama API."""
        url = f"{OLLAMA_BASE}{path}"
        if data:
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=body,
                                        headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))

    def _ollama_running(self) -> bool:
        """Check if Ollama is running."""
        try:
            self._ollama_request("/api/tags", timeout=3)
            return True
        except Exception:
            return False

    def _get_available_models(self) -> set[str]:
        """Get set of available model names."""
        try:
            data = self._ollama_request("/api/tags", timeout=5)
            return {m.get("name", "") for m in data.get("models", [])}
        except Exception:
            return set()

    # ------------------------------------------------------------------
    # Model Building
    # ------------------------------------------------------------------

    def build_model(self, model_name: str) -> dict:
        """Build a single SLATE model from its Modelfile."""
        if model_name not in SLATE_MODELS:
            return {"success": False, "error": f"Unknown model: {model_name}"}

        config = SLATE_MODELS[model_name]
        modelfile_path = self.models_dir / config["modelfile"]

        if not modelfile_path.exists():
            return {"success": False, "error": f"Modelfile not found: {modelfile_path}"}

        # Check base model exists
        available = self._get_available_models()
        if config["base"] not in available:
            self._log(f"Base model {config['base']} not found, pulling...", "WARN")
            try:
                subprocess.run(
                    ["ollama", "pull", config["base"]],
                    timeout=600, check=True,
                    capture_output=True, text=True,
                )
            except Exception as e:
                return {"success": False, "error": f"Failed to pull base: {e}"}

        self._log(f"Building {model_name} from {config['modelfile']}...")
        start = time.time()

        try:
            # Use ollama create with -f flag pointing to Modelfile
            # Note: FROM directives must NOT use colon (:) in model names
            # on Windows, as Windows treats colons as drive letter separators
            result = subprocess.run(
                ["ollama", "create", model_name, "-f",
                 str(modelfile_path.relative_to(self.workspace))],
                capture_output=True, text=True, timeout=600,
                cwd=str(self.workspace),
                encoding="utf-8", errors="replace",
            )

            elapsed = time.time() - start

            if result.returncode == 0:
                self._log(f"Built {model_name} in {elapsed:.1f}s")
                self.state["models_built"][model_name] = {
                    "built_at": datetime.now(timezone.utc).isoformat(),
                    "base": config["base"],
                    "build_time_s": round(elapsed, 1),
                    "modelfile": config["modelfile"],
                }
                self.state["last_build"] = datetime.now(timezone.utc).isoformat()
                self.state["build_history"].append({
                    "model": model_name,
                    "time": datetime.now(timezone.utc).isoformat(),
                    "success": True,
                    "elapsed_s": round(elapsed, 1),
                })
                if len(self.state["build_history"]) > 50:
                    self.state["build_history"] = self.state["build_history"][-50:]
                self._save_state()
                return {"success": True, "model": model_name, "elapsed_s": round(elapsed, 1)}
            else:
                error = result.stderr.strip()[:200]
                self._log(f"Build failed for {model_name}: {error}", "ERROR")
                return {"success": False, "error": error}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Build timed out (600s)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def build_all(self) -> dict:
        """Build all SLATE models."""
        if not self._ollama_running():
            self._log("Ollama not running!", "ERROR")
            return {"success": False, "error": "Ollama not running"}

        results = {}
        # Build in priority order
        ordered = sorted(SLATE_MODELS.items(), key=lambda x: x[1]["priority"])

        for model_name, _ in ordered:
            self._log(f"\n{'='*50}")
            self._log(f"Building: {model_name}")
            self._log(f"{'='*50}")
            result = self.build_model(model_name)
            results[model_name] = result
            if not result.get("success"):
                self._log(f"Failed: {result.get('error', '?')}", "ERROR")

        success_count = sum(1 for r in results.values() if r.get("success"))
        self._log(f"\nBuild complete: {success_count}/{len(SLATE_MODELS)} models built")
        return {"success": success_count == len(SLATE_MODELS), "results": results}

    # ------------------------------------------------------------------
    # Model Testing
    # ------------------------------------------------------------------

    def test_model(self, model_name: str) -> dict:
        """Test a built model with its test prompt."""
        if model_name not in SLATE_MODELS:
            return {"success": False, "error": f"Unknown model: {model_name}"}

        config = SLATE_MODELS[model_name]
        available = self._get_available_models()

        # Check for both exact match and :latest variant
        if model_name not in available and f"{model_name}:latest" not in available:
            return {"success": False, "error": f"Model {model_name} not built yet"}

        actual_name = model_name if model_name in available else f"{model_name}:latest"
        self._log(f"Testing {actual_name}...")

        start = time.time()
        try:
            data = {
                "model": actual_name,
                "prompt": config["test_prompt"],
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 256},
            }
            result = self._ollama_request("/api/generate", data, timeout=120)
            elapsed = time.time() - start

            response = result.get("response", "").lower()
            eval_count = result.get("eval_count", 0)
            eval_ns = result.get("eval_duration", 1)
            tok_per_sec = eval_count / max(eval_ns / 1e9, 0.001)

            # Check expected keywords
            keywords_found = sum(
                1 for kw in config.get("expected_keywords", [])
                if kw.lower() in response
            )
            total_keywords = len(config.get("expected_keywords", []))
            keyword_score = keywords_found / max(total_keywords, 1)

            test_result = {
                "success": True,
                "model": actual_name,
                "tokens": eval_count,
                "tok_per_sec": round(tok_per_sec, 1),
                "elapsed_s": round(elapsed, 1),
                "response_preview": result.get("response", "")[:200],
                "keyword_score": round(keyword_score, 2),
                "keywords_found": keywords_found,
                "keywords_total": total_keywords,
            }

            self.state["test_results"][model_name] = {
                **test_result,
                "tested_at": datetime.now(timezone.utc).isoformat(),
            }
            self.state["last_test"] = datetime.now(timezone.utc).isoformat()
            self._save_state()

            self._log(f"  {actual_name}: {eval_count} tokens @ {tok_per_sec:.1f} tok/s, "
                       f"keywords {keywords_found}/{total_keywords}")
            return test_result

        except Exception as e:
            return {"success": False, "error": str(e), "model": model_name}

    def test_all(self) -> dict:
        """Test all built SLATE models."""
        if not self._ollama_running():
            return {"success": False, "error": "Ollama not running"}

        results = {}
        for model_name in SLATE_MODELS:
            result = self.test_model(model_name)
            results[model_name] = result

        success_count = sum(1 for r in results.values() if r.get("success"))
        return {"success": success_count > 0, "results": results, "passed": success_count}

    # ------------------------------------------------------------------
    # Benchmarking
    # ------------------------------------------------------------------

    def benchmark(self) -> dict:
        """Benchmark all SLATE models side-by-side."""
        if not self._ollama_running():
            return {"success": False, "error": "Ollama not running"}

        prompts = {
            "code_gen": "Write a Python function to check GPU memory usage using nvidia-smi subprocess",
            "classify": "Classify: Add retry logic to the runner API HTTP requests",
            "plan": "Break down: Implement a codebase semantic search using embeddings",
            "review": "Review: def check(): return subprocess.run(['nvidia-smi'], capture_output=True).returncode == 0",
        }

        results = {}
        available = self._get_available_models()

        for model_name in SLATE_MODELS:
            actual = model_name if model_name in available else f"{model_name}:latest"
            if actual not in available:
                results[model_name] = {"status": "not_built"}
                continue

            model_results = {}
            for prompt_name, prompt in prompts.items():
                try:
                    start = time.time()
                    data = {
                        "model": actual,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 256},
                    }
                    r = self._ollama_request("/api/generate", data, timeout=120)
                    elapsed = time.time() - start
                    eval_count = r.get("eval_count", 0)
                    eval_ns = r.get("eval_duration", 1)
                    model_results[prompt_name] = {
                        "tokens": eval_count,
                        "tok_per_sec": round(eval_count / max(eval_ns / 1e9, 0.001), 1),
                        "elapsed_s": round(elapsed, 1),
                    }
                except Exception as e:
                    model_results[prompt_name] = {"error": str(e)[:80]}

            results[model_name] = model_results

        return results

    # ------------------------------------------------------------------
    # Context Update
    # ------------------------------------------------------------------

    def update_context(self) -> dict:
        """Update Modelfiles with latest codebase context and rebuild."""
        self._log("Updating model context from codebase...")

        # Gather current project state for context injection
        project_info = self._gather_project_state()

        # Read and update slate-coder Modelfile with fresh context
        coder_mf = self.models_dir / "Modelfile.slate-coder"
        if coder_mf.exists():
            content = coder_mf.read_text(encoding="utf-8")

            # Find and update the dynamic context section if it exists
            marker = "## Current Project State"
            if marker in content:
                # Replace existing dynamic section
                idx = content.index(marker)
                end_marker = '"""'
                end_idx = content.index(end_marker, idx)
                content = content[:idx] + project_info + "\n" + content[end_idx:]
            else:
                # Insert before closing triple-quote of SYSTEM
                last_quote = content.rfind('"""')
                if last_quote > 0:
                    content = content[:last_quote] + "\n" + project_info + "\n" + content[last_quote:]

            coder_mf.write_text(content, encoding="utf-8")
            self._log("Updated slate-coder Modelfile with project state")

        # Rebuild all
        return self.build_all()

    def _gather_project_state(self) -> str:
        """Gather current project state for model context."""
        lines = ["## Current Project State"]

        # Count files
        slate_files = list((self.workspace / "slate").glob("*.py"))
        agent_files = list((self.workspace / "agents").glob("*.py"))
        test_files = list((self.workspace / "tests").rglob("*.py"))
        workflow_files = list((self.workspace / ".github" / "workflows").glob("*.yml"))

        lines.append(f"- Core modules: {len(slate_files)} files in slate/")
        lines.append(f"- Agent modules: {len(agent_files)} files in agents/")
        lines.append(f"- Test files: {len(test_files)} files in tests/")
        lines.append(f"- Workflows: {len(workflow_files)} files in .github/workflows/")

        # Current tasks
        task_file = self.workspace / "current_tasks.json"
        if task_file.exists():
            try:
                data = json.loads(task_file.read_text(encoding="utf-8"))
                tasks = data.get("tasks", [])
                pending = [t for t in tasks if t.get("status") == "pending"]
                completed = [t for t in tasks if t.get("status") == "completed"]
                lines.append(f"- Pending tasks: {len(pending)}")
                lines.append(f"- Completed tasks: {len(completed)}")
            except Exception:
                pass

        # Module listing
        lines.append("\n### Key Modules")
        for py in sorted(slate_files, key=lambda p: p.name):
            lines.append(f"- {py.name}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Get model trainer status."""
        available = self._get_available_models() if self._ollama_running() else set()

        model_status = {}
        for name, config in SLATE_MODELS.items():
            built = name in available or f"{name}:latest" in available
            model_status[name] = {
                "built": built,
                "base": config["base"],
                "purpose": config["purpose"],
                "gpu": config["gpu"],
                "build_info": self.state.get("models_built", {}).get(name, {}),
                "test_info": self.state.get("test_results", {}).get(name, {}),
            }

        return {
            "ollama_running": self._ollama_running(),
            "models": model_status,
            "total_built": sum(1 for m in model_status.values() if m["built"]),
            "total_models": len(SLATE_MODELS),
            "last_build": self.state.get("last_build"),
            "last_test": self.state.get("last_test"),
            "build_history": self.state.get("build_history", [])[-5:],
        }

    def print_status(self):
        """Print human-readable status."""
        status = self.get_status()

        print("=" * 65)
        print("  SLATE Model Trainer")
        print("=" * 65)
        print(f"\n  Ollama:      {'Running' if status['ollama_running'] else 'STOPPED'}")
        print(f"  Models Built: {status['total_built']}/{status['total_models']}")
        print(f"  Last Build:   {status.get('last_build', 'Never')}")
        print(f"  Last Test:    {status.get('last_test', 'Never')}")

        print("\n  Models:")
        for name, info in status["models"].items():
            icon = "+" if info["built"] else "x"
            gpu = f"GPU {info['gpu']}"
            print(f"    [{icon}] {name:20s} ({info['base']:20s}) {gpu:6s}  {info['purpose']}")
            if info.get("test_info", {}).get("tok_per_sec"):
                t = info["test_info"]
                print(f"        Last test: {t['tok_per_sec']} tok/s, "
                      f"keywords {t.get('keywords_found', '?')}/{t.get('keywords_total', '?')}")

        if status.get("build_history"):
            print("\n  Recent Builds:")
            for h in status["build_history"]:
                icon = "+" if h.get("success") else "x"
                print(f"    [{icon}] {h['model']:20s} {h.get('elapsed_s', '?')}s  {h.get('time', '')[:19]}")

        print("\n" + "=" * 65)

    def print_benchmark(self):
        """Run and print benchmarks."""
        print("Running SLATE model benchmarks...\n")
        results = self.benchmark()

        print(f"{'Model':<20} {'Task':<12} {'Tokens':<8} {'Speed':<12} {'Time':<8}")
        print("-" * 60)
        for model, tasks in results.items():
            if tasks.get("status") == "not_built":
                print(f"{model:<20} {'NOT BUILT':<12}")
                continue
            for task, r in tasks.items():
                if "error" in r:
                    print(f"{model:<20} {task:<12} {'ERROR':<8} {r['error'][:20]}")
                else:
                    print(f"{model:<20} {task:<12} {r['tokens']:<8} "
                          f"{r['tok_per_sec']} tok/s  {r['elapsed_s']}s")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="SLATE Model Trainer")
    parser.add_argument("--build-all", action="store_true", help="Build all SLATE models")
    parser.add_argument("--build", type=str, help="Build specific model (slate-coder, slate-fast, slate-planner)")
    parser.add_argument("--test", action="store_true", help="Test all built models")
    parser.add_argument("--test-model", type=str, help="Test specific model")
    parser.add_argument("--benchmark", action="store_true", help="Benchmark all models")
    parser.add_argument("--update-context", action="store_true", help="Update models with latest codebase context")
    parser.add_argument("--status", action="store_true", help="Show model status")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    trainer = SlateModelTrainer()

    if args.build_all:
        trainer.build_all()
    elif args.build:
        result = trainer.build_model(args.build)
        if result["success"]:
            print(f"Built {args.build} in {result['elapsed_s']}s")
        else:
            print(f"FAILED: {result['error']}")
            sys.exit(1)
    elif args.test:
        trainer.test_all()
    elif args.test_model:
        result = trainer.test_model(args.test_model)
        print(json.dumps(result, indent=2, default=str))
    elif args.benchmark:
        trainer.print_benchmark()
    elif args.update_context:
        trainer.update_context()
    elif args.json:
        print(json.dumps(trainer.get_status(), indent=2, default=str))
    else:
        trainer.print_status()


if __name__ == "__main__":
    main()
