#!/usr/bin/env python3
"""
SLATE ML Orchestrator - Local GPU Inference Management
======================================================
# Modified: 2026-02-07T04:30:00Z | Author: COPILOT | Change: Initial implementation

Manages local ML inference using Ollama and PyTorch on dual GPUs.
Provides model routing, embedding indexing, and inference APIs for
the SLATE agentic system.

Features:
- Ollama model management (load/unload/route)
- GPU memory-aware model placement
- Embedding index for codebase semantic search
- Inference API for agent task processing
- Training pipeline for local fine-tuning

Usage:
    python slate/ml_orchestrator.py --start          # Start ML services
    python slate/ml_orchestrator.py --status         # Show ML status
    python slate/ml_orchestrator.py --train-now      # Trigger training
    python slate/ml_orchestrator.py --index-now      # Rebuild embeddings
    python slate/ml_orchestrator.py --benchmarks     # Run inference benchmarks
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

# Modified: 2026-02-07T04:30:00Z | Author: COPILOT | Change: workspace setup
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

OLLAMA_BASE = "http://127.0.0.1:11434"
STATE_FILE = WORKSPACE_ROOT / ".slate_ml_state.json"
EMBEDDINGS_DIR = WORKSPACE_ROOT / "slate_memory" / "embeddings"

# Modified: 2026-02-07T06:00:00Z | Author: COPILOT | Change: SLATE model routing with dual-GPU
# Model routing: task type -> preferred model (SLATE custom models preferred)
MODEL_ROUTING = {
    "code_generation": "slate-coder:latest",        # 12B SLATE-tuned code gen (GPU 0)
    "code_review": "slate-coder:latest",            # 12B SLATE-tuned review (GPU 0)
    "summarization": "slate-fast:latest",           # 3B SLATE-tuned summaries (GPU 1)
    "classification": "slate-fast:latest",          # 3B SLATE-tuned classification (GPU 1)
    "embedding": "nomic-embed-text:latest",         # 137M embeddings (GPU 1)
    "general": "slate-planner:latest",              # 7B SLATE-tuned general (GPU 0/1)
    "planning": "slate-planner:latest",             # 7B SLATE-tuned planning
    "quick": "slate-fast:latest",                   # 3B SLATE-tuned fast (GPU 1)
}

# Fallback routing: if SLATE models not built, use base models
FALLBACK_ROUTING = {
    "slate-coder:latest": "mistral-nemo:latest",
    "slate-fast:latest": "llama3.2:3b",
    "slate-planner:latest": "mistral:latest",
}

# GPU placement strategy — dual RTX 5070 Ti (16GB each)
GPU_STRATEGY = {
    0: {
        "role": "primary_inference",
        "max_vram_mb": 14000,
        "preferred_models": ["slate-coder:latest", "slate-planner:latest",
                             "mistral-nemo:latest", "mistral:latest"],
    },
    1: {
        "role": "secondary_inference",
        "max_vram_mb": 14000,
        "preferred_models": ["slate-fast:latest", "nomic-embed-text:latest",
                             "llama3.2:3b", "phi:latest"],
    },
}


class OllamaClient:
    """Client for interacting with local Ollama instance."""

    # Modified: 2026-02-07T04:30:00Z | Author: COPILOT | Change: Ollama API client
    def __init__(self, base_url: str = OLLAMA_BASE):
        self.base_url = base_url

    def _request(self, path: str, data: dict | None = None, timeout: int = 120) -> dict:
        """Make a request to Ollama API."""
        url = f"{self.base_url}{path}"
        if data:
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))

    def is_running(self) -> bool:
        """Check if Ollama is running."""
        try:
            self._request("/api/tags", timeout=3)
            return True
        except Exception:
            return False

    def list_models(self) -> list[dict]:
        """List available models."""
        try:
            data = self._request("/api/tags", timeout=5)
            return data.get("models", [])
        except Exception:
            return []

    def running_models(self) -> list[dict]:
        """List currently loaded models."""
        try:
            data = self._request("/api/ps", timeout=5)
            return data.get("models", [])
        except Exception:
            return []

    def generate(self, model: str, prompt: str, system: str = "",
                 temperature: float = 0.7, max_tokens: int = 2048,
                 stream: bool = False, keep_alive: str = "24h") -> dict:
        """Generate text with a model."""
        # Modified: 2026-02-07T08:00:00Z | Author: COPILOT | Change: Added keep_alive for GPU persistence
        data = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "keep_alive": keep_alive,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            data["system"] = system
        return self._request("/api/generate", data, timeout=300)

    def embed(self, model: str, text: str) -> list[float]:
        """Generate embeddings for text."""
        # Modified: 2026-02-07T08:00:00Z | Author: COPILOT | Change: Added keep_alive
        data = {"model": model, "input": text, "keep_alive": "24h"}
        result = self._request("/api/embed", data, timeout=60)
        embeddings = result.get("embeddings", [[]])
        return embeddings[0] if embeddings else []

    def chat(self, model: str, messages: list[dict], temperature: float = 0.7) -> dict:
        """Chat completion."""
        data = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        return self._request("/api/chat", data, timeout=300)


class MLOrchestrator:
    """Orchestrates local ML inference for SLATE agents."""

    # Modified: 2026-02-07T04:30:00Z | Author: COPILOT | Change: ML orchestrator core
    def __init__(self):
        self.ollama = OllamaClient()
        self.workspace = WORKSPACE_ROOT
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """Load orchestrator state."""
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return {
            "started_at": None,
            "total_inferences": 0,
            "total_embeddings": 0,
            "model_stats": {},
            "last_index": None,
            "last_train": None,
        }

    def _save_state(self):
        """Save orchestrator state."""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(self.state, indent=2, default=str), encoding="utf-8")

    # ------------------------------------------------------------------
    # Model Management
    # ------------------------------------------------------------------

    def get_model_for_task(self, task_type: str) -> str:
        """Route a task to the best available model, preferring SLATE models."""
        model = MODEL_ROUTING.get(task_type, MODEL_ROUTING["general"])
        # Verify model is available
        available = {m.get("name") for m in self.ollama.list_models()}
        if model in available:
            return model
        # Try SLATE model fallback (SLATE model -> base model)
        fallback = FALLBACK_ROUTING.get(model)
        if fallback and fallback in available:
            return fallback
        # Generic fallback chain
        for fb in ["mistral-nemo:latest", "mistral:latest", "llama3.2:3b", "phi:latest"]:
            if fb in available:
                return fb
        raise RuntimeError("No Ollama models available")

    def ensure_slate_models(self) -> dict:
        """Build SLATE models if not already built."""
        available = {m.get("name") for m in self.ollama.list_models()}
        needed = []
        for model in ["slate-coder:latest", "slate-fast:latest", "slate-planner:latest"]:
            if model not in available:
                needed.append(model)

        if not needed:
            return {"status": "all_built", "models": 3}

        # Build missing models via trainer
        try:
            from slate.slate_model_trainer import SlateModelTrainer
            trainer = SlateModelTrainer()
            results = {}
            for model in needed:
                name = model.replace(":latest", "")
                results[name] = trainer.build_model(name)
            built = sum(1 for r in results.values() if r.get("success"))
            return {"status": "built", "built": built, "total": len(needed), "results": results}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def preload_models(self, task_types: list[str] | None = None):
        """Preload models for expected task types."""
        if not task_types:
            task_types = ["quick", "embedding", "code_generation"]

        for task_type in task_types:
            model = self.get_model_for_task(task_type)
            print(f"  Preloading {model} for {task_type}...")
            try:
                # Warm up with a tiny inference
                self.ollama.generate(model, "hello", max_tokens=1)
                print(f"    Loaded {model}")
            except Exception as e:
                print(f"    Failed: {e}")

    # ------------------------------------------------------------------
    # Inference API
    # ------------------------------------------------------------------

    def infer(self, prompt: str, task_type: str = "general",
              system: str = "", temperature: float = 0.7,
              max_tokens: int = 2048) -> dict:
        """Run inference with automatic model routing."""
        model = self.get_model_for_task(task_type)
        start = time.time()
        result = self.ollama.generate(model, prompt, system=system,
                                       temperature=temperature,
                                       max_tokens=max_tokens)
        elapsed = time.time() - start

        # Track stats
        self.state["total_inferences"] += 1
        if model not in self.state["model_stats"]:
            self.state["model_stats"][model] = {"calls": 0, "tokens": 0, "time": 0}
        stats = self.state["model_stats"][model]
        stats["calls"] += 1
        stats["tokens"] += result.get("eval_count", 0)
        stats["time"] += elapsed
        self._save_state()

        return {
            "response": result.get("response", ""),
            "model": model,
            "task_type": task_type,
            "tokens": result.get("eval_count", 0),
            "eval_time": result.get("eval_duration", 0) / 1e9,
            "total_time": elapsed,
            "tok_per_sec": result.get("eval_count", 0) / max(result.get("eval_duration", 1) / 1e9, 0.001),
        }

    def analyze_code(self, code: str, instruction: str = "Review this code") -> dict:
        """Analyze code using the code review model."""
        prompt = f"{instruction}:\n\n```\n{code}\n```"
        return self.infer(prompt, task_type="code_review",
                         system="You are a senior code reviewer. Be concise and actionable.")

    def generate_code(self, description: str, language: str = "python") -> dict:
        """Generate code from a description."""
        prompt = f"Write {language} code for: {description}"
        return self.infer(prompt, task_type="code_generation",
                         system=f"You are an expert {language} developer. Output only code, no explanation.")

    def classify_task(self, task_description: str) -> dict:
        """Classify a task into agent routing categories."""
        system = """Classify the task into exactly one category. Reply with ONLY the category name.
Categories: implement, test, analyze, integrate, complex"""
        result = self.infer(task_description, task_type="classification",
                           system=system, temperature=0.1, max_tokens=20)
        category = result["response"].strip().lower()
        # Map to agent
        agent_map = {
            "implement": "ALPHA", "code": "ALPHA", "build": "ALPHA", "fix": "ALPHA",
            "test": "BETA", "validate": "BETA", "verify": "BETA",
            "analyze": "GAMMA", "plan": "GAMMA", "research": "GAMMA",
            "integrate": "DELTA", "mcp": "DELTA", "sdk": "DELTA",
            "complex": "COPILOT",
        }
        agent = agent_map.get(category, "ALPHA")
        result["classification"] = category
        result["routed_agent"] = agent
        return result

    def summarize(self, text: str, max_words: int = 100) -> dict:
        """Summarize text."""
        prompt = f"Summarize in {max_words} words or fewer:\n\n{text}"
        return self.infer(prompt, task_type="summarization",
                         system="Be concise. Output only the summary.",
                         temperature=0.3, max_tokens=200)

    # ------------------------------------------------------------------
    # Embeddings & Indexing
    # ------------------------------------------------------------------

    def embed_text(self, text: str) -> list[float]:
        """Generate embeddings for text."""
        self.state["total_embeddings"] += 1
        self._save_state()
        return self.ollama.embed("nomic-embed-text:latest", text)

    def index_codebase(self, extensions: list[str] | None = None,
                       dirs: list[str] | None = None) -> dict:
        # Modified: 2026-02-06T22:30:00Z | Author: COPILOT | Change: Use ChromaDB for persistent vector storage
        """Build embedding index of the codebase using ChromaDB."""
        try:
            from slate.slate_chromadb import SlateChromaDB
            chromadb_store = SlateChromaDB()
            print("  Using ChromaDB persistent vector store")
            result = chromadb_store.index_all(incremental=True)
            self.state["last_index"] = datetime.now(timezone.utc).isoformat()
            self._save_state()
            return result
        except ImportError:
            print("  ChromaDB not available, falling back to flat-file index")
        except Exception as e:
            print(f"  ChromaDB error ({e}), falling back to flat-file index")

        # Fallback: flat-file JSON index
        if not extensions:
            extensions = [".py", ".ts", ".yml", ".yaml", ".md"]
        if not dirs:
            dirs = ["slate", "agents", "plugins", ".github/workflows", "skills"]

        EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
        index = {"files": [], "built_at": datetime.now(timezone.utc).isoformat()}
        total_files = 0
        total_chunks = 0

        for dir_name in dirs:
            dir_path = self.workspace / dir_name
            if not dir_path.exists():
                continue
            for ext in extensions:
                for file_path in dir_path.rglob(f"*{ext}"):
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="replace")
                        chunks = self._chunk_text(content, max_chars=500)
                        embeddings = []
                        for chunk in chunks:
                            emb = self.embed_text(chunk)
                            embeddings.append({"text": chunk[:200], "embedding": emb[:10]})
                            total_chunks += 1

                        rel_path = str(file_path.relative_to(self.workspace))
                        index["files"].append({
                            "path": rel_path,
                            "chunks": len(chunks),
                            "size": len(content),
                        })
                        total_files += 1
                    except Exception as e:
                        print(f"  Skip {file_path}: {e}")

        index["total_files"] = total_files
        index["total_chunks"] = total_chunks

        index_path = EMBEDDINGS_DIR / "index.json"
        index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

        self.state["last_index"] = datetime.now(timezone.utc).isoformat()
        self._save_state()

        print(f"Indexed {total_files} files, {total_chunks} chunks")
        return index

    def _chunk_text(self, text: str, max_chars: int = 500) -> list[str]:
        """Split text into chunks."""
        lines = text.split("\n")
        chunks = []
        current = []
        current_len = 0
        for line in lines:
            if current_len + len(line) > max_chars and current:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            current.append(line)
            current_len += len(line) + 1
        if current:
            chunks.append("\n".join(current))
        return chunks or [text[:max_chars]]

    # ------------------------------------------------------------------
    # Benchmarks
    # ------------------------------------------------------------------

    def run_benchmarks(self) -> dict:
        """Run inference benchmarks across all models."""
        results = {}
        test_prompt = "Explain what a Python decorator does in 2 sentences."

        for model_info in self.ollama.list_models():
            model = model_info.get("name", "")
            if "embed" in model:
                # Test embedding
                start = time.time()
                emb = self.embed_text("Test embedding for benchmark")
                elapsed = time.time() - start
                results[model] = {
                    "type": "embedding",
                    "dimensions": len(emb),
                    "time_s": round(elapsed, 3),
                }
            else:
                # Test generation
                try:
                    start = time.time()
                    result = self.ollama.generate(model, test_prompt, max_tokens=100)
                    elapsed = time.time() - start
                    eval_count = result.get("eval_count", 0)
                    eval_ns = result.get("eval_duration", 1)
                    results[model] = {
                        "type": "generation",
                        "tokens": eval_count,
                        "eval_time_s": round(eval_ns / 1e9, 3),
                        "total_time_s": round(elapsed, 3),
                        "tok_per_sec": round(eval_count / max(eval_ns / 1e9, 0.001), 1),
                    }
                except Exception as e:
                    results[model] = {"type": "error", "error": str(e)}

        return results

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Get full ML orchestrator status."""
        ollama_running = self.ollama.is_running()
        models = self.ollama.list_models() if ollama_running else []
        running = self.ollama.running_models() if ollama_running else []

        # GPU info
        gpu_info = []
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total,utilization.gpu",
                 "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10
            )
            for line in r.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    gpu_info.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "memory_used": parts[2],
                        "memory_total": parts[3],
                        "utilization": parts[4],
                    })
        except Exception:
            pass

        # PyTorch check
        pytorch_status = {"installed": False}
        try:
            import torch
            pytorch_status = {
                "installed": True,
                "version": torch.__version__,
                "cuda_available": torch.cuda.is_available(),
                "gpu_count": torch.cuda.device_count(),
            }
        except ImportError:
            pass

        return {
            "ollama": {
                "running": ollama_running,
                "models_available": len(models),
                "models_loaded": len(running),
                "models": [
                    {
                        "name": m.get("name"),
                        "size_gb": round(m.get("size", 0) / 1e9, 1),
                        "family": m.get("details", {}).get("family", "?"),
                        "params": m.get("details", {}).get("parameter_size", "?"),
                    }
                    for m in models
                ],
                "loaded": [
                    {
                        "name": m.get("name"),
                        "vram_gb": round(m.get("size_vram", 0) / 1e9, 1),
                        "gpu_offload": round(m.get("size_vram", 0) / max(m.get("size", 1), 1) * 100),
                    }
                    for m in running
                ],
            },
            "gpu": gpu_info,
            "pytorch": pytorch_status,
            "stats": {
                "total_inferences": self.state.get("total_inferences", 0),
                "total_embeddings": self.state.get("total_embeddings", 0),
                "last_index": self.state.get("last_index"),
                "model_stats": self.state.get("model_stats", {}),
            },
            "routing": MODEL_ROUTING,
        }

    def print_status(self):
        """Print human-readable status."""
        status = self.get_status()
        print("=" * 60)
        print("  SLATE ML Orchestrator")
        print("=" * 60)

        # Ollama
        o = status["ollama"]
        state = "RUNNING" if o["running"] else "STOPPED"
        print(f"\n  Ollama:     {state}")
        print(f"  Models:     {o['models_available']} available, {o['models_loaded']} loaded")
        for m in o["models"]:
            print(f"              - {m['name']} ({m['size_gb']}GB, {m['family']}, {m['params']})")
        if o["loaded"]:
            print("  In VRAM:")
            for m in o["loaded"]:
                print(f"              - {m['name']} ({m['vram_gb']}GB, {m['gpu_offload']}% GPU)")

        # GPUs
        print()
        for g in status["gpu"]:
            print(f"  GPU {g['index']}:     {g['name']}")
            print(f"              Memory: {g['memory_used']} / {g['memory_total']}, Util: {g['utilization']}")

        # PyTorch
        pt = status["pytorch"]
        if pt["installed"]:
            print(f"\n  PyTorch:    {pt['version']} (CUDA: {pt['cuda_available']}, GPUs: {pt['gpu_count']})")
        else:
            print("\n  PyTorch:    NOT INSTALLED")

        # Stats
        s = status["stats"]
        print(f"\n  Inferences: {s['total_inferences']}")
        print(f"  Embeddings: {s['total_embeddings']}")
        if s["last_index"]:
            print(f"  Last Index: {s['last_index']}")

        # Model stats
        if s["model_stats"]:
            print("\n  Model Performance:")
            for model, ms in s["model_stats"].items():
                avg_tps = ms["tokens"] / max(ms["time"], 0.001)
                print(f"    {model}: {ms['calls']} calls, {ms['tokens']} tokens, {avg_tps:.0f} avg tok/s")

        print("\n" + "=" * 60)

    def print_benchmarks(self):
        """Run and print benchmarks."""
        print("Running inference benchmarks...\n")
        results = self.run_benchmarks()
        print(f"{'Model':<30} {'Type':<12} {'Tokens':<8} {'Time':<8} {'Speed':<12}")
        print("-" * 70)
        for model, r in results.items():
            if r["type"] == "generation":
                print(f"{model:<30} {'gen':<12} {r['tokens']:<8} {r['total_time_s']:<8} {r['tok_per_sec']} tok/s")
            elif r["type"] == "embedding":
                print(f"{model:<30} {'embed':<12} {r['dimensions']:<8} {r['time_s']:<8} {'N/A':<12}")
            else:
                print(f"{model:<30} {'ERROR':<12} {'':<8} {'':<8} {r.get('error','')[:20]}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="SLATE ML Orchestrator")
    parser.add_argument("--start", action="store_true", help="Start ML services (preload models)")
    parser.add_argument("--warmup", action="store_true", help="Full system warmup (configure + preload + index)")
    parser.add_argument("--status", action="store_true", help="Show ML status")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--train-now", action="store_true", help="Trigger training/fine-tune")
    parser.add_argument("--index-now", action="store_true", help="Rebuild embedding index")
    parser.add_argument("--benchmarks", action="store_true", help="Run inference benchmarks")
    parser.add_argument("--infer", type=str, help="Run inference with prompt")
    parser.add_argument("--task-type", type=str, default="general", help="Task type for routing")
    args = parser.parse_args()

    orch = MLOrchestrator()

    if args.start:
        print("Starting SLATE ML Orchestrator...")
        if not orch.ollama.is_running():
            print("  ERROR: Ollama is not running. Start it first.")
            sys.exit(1)
        orch.preload_models()
        print("\nML Orchestrator ready.")
        orch.print_status()
    elif args.warmup:
        # Modified: 2026-02-07T08:00:00Z | Author: COPILOT | Change: warmup integration
        print("Running full SLATE warmup...")
        from slate.slate_warmup import SlateWarmup
        warmup = SlateWarmup()
        warmup.warmup()
    elif args.index_now:
        print("Building codebase embedding index...")
        orch.index_codebase()
    elif args.train_now:
        print("Building SLATE custom models...")
        # Build all SLATE models
        model_result = orch.ensure_slate_models()
        if model_result.get("status") == "all_built":
            print("All SLATE models already built!")
        elif model_result.get("status") == "built":
            print(f"Built {model_result['built']}/{model_result['total']} models")
        else:
            print(f"Error: {model_result.get('error', 'unknown')}")
            sys.exit(1)
        # Test the models
        print("\nTesting SLATE models...")
        try:
            from slate.slate_model_trainer import SlateModelTrainer
            trainer = SlateModelTrainer()
            test_results = trainer.test_all()
            print(f"Tests passed: {test_results.get('passed', 0)}/{len(test_results.get('results', {}))}")
        except Exception as e:
            print(f"Test error: {e}")
        orch.print_status()
    elif args.benchmarks:
        orch.print_benchmarks()
    elif args.infer:
        result = orch.infer(args.infer, task_type=args.task_type)
        print(f"Model: {result['model']}")
        print(f"Speed: {result['tok_per_sec']:.1f} tok/s ({result['tokens']} tokens)")
        print(f"Response:\n{result['response']}")
    elif args.json:
        print(json.dumps(orch.get_status(), indent=2, default=str))
    else:
        orch.print_status()


if __name__ == "__main__":
    main()
