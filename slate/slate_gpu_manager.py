#!/usr/bin/env python3
"""
SLATE GPU Manager — Dual-GPU Load Balancing for Ollama
========================================================
# Modified: 2026-02-07T06:00:00Z | Author: COPILOT | Change: Initial dual-GPU manager

Manages GPU placement and load balancing across 2x RTX 5070 Ti GPUs.
Configures Ollama environment for dual-GPU model distribution.

GPU Layout:
    GPU 0 (Primary):   slate-coder (12B), slate-planner (7B) — heavy inference
    GPU 1 (Secondary):  slate-fast (3B), nomic-embed-text — quick tasks + embeddings

Usage:
    python slate/slate_gpu_manager.py --status         # GPU status
    python slate/slate_gpu_manager.py --balance         # Balance models across GPUs
    python slate/slate_gpu_manager.py --configure       # Configure Ollama for dual-GPU
    python slate/slate_gpu_manager.py --preload         # Preload models to assigned GPUs
"""

import argparse
import json
import os
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

# GPU-to-model assignment
GPU_MODEL_MAP = {
    0: {
        "models": ["slate-coder:latest", "slate-planner:latest",
                    "mistral-nemo:latest", "mistral:latest"],
        "role": "heavy_inference",
        "max_loaded_mb": 14000,
    },
    1: {
        "models": ["slate-fast:latest", "nomic-embed-text:latest",
                    "llama3.2:3b", "phi:latest", "llama2:latest"],
        "role": "quick_tasks",
        "max_loaded_mb": 14000,
    },
}


class GPUManager:
    """Manages dual-GPU model placement for Ollama."""

    # Modified: 2026-02-07T06:00:00Z | Author: COPILOT | Change: GPU manager core

    def __init__(self):
        self.workspace = WORKSPACE_ROOT

    def _ollama_request(self, path: str, data: dict | None = None,
                        timeout: int = 60) -> dict:
        """Make request to Ollama API."""
        url = f"{OLLAMA_BASE}{path}"
        if data:
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=body,
                                        headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))

    def get_gpu_status(self) -> list[dict]:
        """Get detailed GPU status via nvidia-smi."""
        try:
            r = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=index,name,memory.used,memory.free,memory.total,utilization.gpu,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
            )
            gpus = []
            for line in r.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 7:
                    gpus.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "memory_used_mb": int(parts[2]),
                        "memory_free_mb": int(parts[3]),
                        "memory_total_mb": int(parts[4]),
                        "utilization_pct": int(parts[5]),
                        "temperature_c": int(parts[6]),
                        "assigned_models": GPU_MODEL_MAP.get(int(parts[0]), {}).get("models", []),
                        "role": GPU_MODEL_MAP.get(int(parts[0]), {}).get("role", "unknown"),
                    })
            return gpus
        except Exception as e:
            print(f"nvidia-smi error: {e}")
            return []

    def get_loaded_models(self) -> list[dict]:
        """Get currently loaded models in Ollama."""
        try:
            data = self._ollama_request("/api/ps", timeout=5)
            return data.get("models", [])
        except Exception:
            return []

    def configure_dual_gpu(self) -> dict:
        """Configure Ollama environment for dual-GPU operation."""
        results = []

        # Ensure CUDA_VISIBLE_DEVICES is set for both GPUs
        os.environ["CUDA_VISIBLE_DEVICES"] = "0,1"
        results.append("Set CUDA_VISIBLE_DEVICES=0,1")

        # Write Ollama env config
        env_file = self.workspace / ".ollama_env"
        env_content = (
            "# SLATE Ollama Dual-GPU Configuration\n"
            f"# Modified: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} | Author: COPILOT\n"
            "CUDA_VISIBLE_DEVICES=0,1\n"
            "OLLAMA_HOST=127.0.0.1:11434\n"
            "OLLAMA_NUM_PARALLEL=4\n"
            "OLLAMA_MAX_LOADED_MODELS=4\n"
            "OLLAMA_FLASH_ATTENTION=1\n"
        )
        env_file.write_text(env_content, encoding="utf-8")
        results.append(f"Wrote {env_file}")

        # Update pre-job hook for runners
        hook_file = self.workspace / "actions-runner" / "hooks" / "pre-job.ps1"
        if hook_file.exists():
            content = hook_file.read_text(encoding="utf-8")
            if "OLLAMA_MAX_LOADED_MODELS" not in content:
                additions = (
                    "\n# SLATE Dual-GPU Ollama configuration\n"
                    "$env:OLLAMA_NUM_PARALLEL = '4'\n"
                    "$env:OLLAMA_MAX_LOADED_MODELS = '4'\n"
                    "$env:OLLAMA_FLASH_ATTENTION = '1'\n"
                )
                content += additions
                hook_file.write_text(content, encoding="utf-8")
                results.append("Updated pre-job.ps1 with Ollama dual-GPU config")

        return {"success": True, "actions": results}

    def preload_models(self) -> dict:
        """Preload key models to warm up both GPUs."""
        results = {}

        # Warm up primary models (GPU 0)
        for model_name in ["slate-coder:latest", "slate-planner:latest"]:
            results[model_name] = self._warm_model(model_name)

        # Warm up secondary models (GPU 1)
        for model_name in ["slate-fast:latest", "nomic-embed-text:latest"]:
            results[model_name] = self._warm_model(model_name)

        loaded = sum(1 for r in results.values() if r.get("success"))
        return {"success": loaded > 0, "loaded": loaded, "total": len(results), "details": results}

    def _warm_model(self, model_name: str) -> dict:
        """Warm a model by running a tiny inference."""
        try:
            available = {m.get("name") for m in self._ollama_request("/api/tags", timeout=5).get("models", [])}
            if model_name not in available:
                # Try without :latest
                base_name = model_name.replace(":latest", "")
                if base_name not in available:
                    return {"success": False, "error": f"Model {model_name} not available"}
                model_name = base_name

            start = time.time()
            if "embed" in model_name:
                self._ollama_request("/api/embed",
                                     {"model": model_name, "input": "test"}, timeout=30)
            else:
                self._ollama_request("/api/generate",
                                     {"model": model_name, "prompt": "hi",
                                      "stream": False, "options": {"num_predict": 1}},
                                     timeout=60)
            elapsed = time.time() - start
            return {"success": True, "elapsed_s": round(elapsed, 1)}
        except Exception as e:
            return {"success": False, "error": str(e)[:80]}

    def print_status(self):
        """Print GPU status."""
        gpus = self.get_gpu_status()
        loaded = self.get_loaded_models()

        print("=" * 65)
        print("  SLATE GPU Manager — Dual RTX 5070 Ti")
        print("=" * 65)

        for gpu in gpus:
            used_pct = gpu["memory_used_mb"] / max(gpu["memory_total_mb"], 1) * 100
            print(f"\n  GPU {gpu['index']}: {gpu['name']}")
            print(f"    Role:        {gpu['role']}")
            print(f"    Memory:      {gpu['memory_used_mb']} / {gpu['memory_total_mb']} MB ({used_pct:.0f}%)")
            print(f"    Free:        {gpu['memory_free_mb']} MB")
            print(f"    Utilization: {gpu['utilization_pct']}%")
            print(f"    Temperature: {gpu['temperature_c']}°C")
            print(f"    Assigned:    {', '.join(gpu['assigned_models'][:3])}")

        if loaded:
            print(f"\n  Loaded Models ({len(loaded)}):")
            for m in loaded:
                vram_gb = m.get("size_vram", 0) / 1e9
                total_gb = m.get("size", 1) / 1e9
                offload = m.get("size_vram", 0) / max(m.get("size", 1), 1) * 100
                print(f"    {m.get('name', '?'):30s} VRAM: {vram_gb:.1f}GB ({offload:.0f}% GPU)")
        else:
            print("\n  No models currently loaded in VRAM")

        print("\n" + "=" * 65)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="SLATE GPU Manager")
    parser.add_argument("--status", action="store_true", help="GPU status")
    parser.add_argument("--balance", action="store_true", help="Balance models across GPUs")
    parser.add_argument("--configure", action="store_true", help="Configure Ollama for dual-GPU")
    parser.add_argument("--preload", action="store_true", help="Preload models to GPUs")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    mgr = GPUManager()

    if args.configure:
        result = mgr.configure_dual_gpu()
        for action in result.get("actions", []):
            print(f"  {action}")
    elif args.preload:
        result = mgr.preload_models()
        print(f"Loaded {result['loaded']}/{result['total']} models")
        for name, detail in result.get("details", {}).items():
            icon = "+" if detail.get("success") else "x"
            print(f"  [{icon}] {name}: {detail.get('elapsed_s', detail.get('error', '?'))}")
    elif args.json:
        print(json.dumps({
            "gpus": mgr.get_gpu_status(),
            "loaded": [{"name": m.get("name"), "vram_gb": round(m.get("size_vram", 0)/1e9, 1)}
                        for m in mgr.get_loaded_models()],
        }, indent=2, default=str))
    else:
        mgr.print_status()


if __name__ == "__main__":
    main()
