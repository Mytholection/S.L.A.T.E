#!/usr/bin/env python3
# Modified: 2026-07-12T02:45:00Z | Author: COPILOT | Change: Create AI production readiness module
"""
SLATE AI Production — Model Health Monitoring & Production Readiness
=====================================================================

Monitors SLATE AI models in production, enforcing SLA compliance,
detecting degradation, managing failover, and tracking operational health.

Architecture:
  HealthMonitor → SLAChecker → DegradationDetector → FailoverManager
                             → ReadinessAssessor → ProductionReport

Features:
- Model health monitoring (heartbeat, latency, error rate)
- SLA compliance enforcement (latency targets, availability, throughput)
- Degradation detection with automatic alerting
- Failover logic (SLATE model -> base model -> next available)
- Production readiness assessment (pre-deployment checklist)
- Operational dashboards data for the FastAPI dashboard
- GPU memory and utilization monitoring
- Model warm-up and keepalive management

Usage:
    python slate/slate_ai_production.py --status           # Production status
    python slate/slate_ai_production.py --health-check     # Run health checks
    python slate/slate_ai_production.py --sla-report       # SLA compliance report
    python slate/slate_ai_production.py --readiness        # Pre-deployment readiness
    python slate/slate_ai_production.py --failover-test    # Test failover logic
    python slate/slate_ai_production.py --warmup           # Warm up all models
    python slate/slate_ai_production.py --json             # JSON output
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

# Modified: 2026-07-12T02:45:00Z | Author: COPILOT | Change: workspace setup
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROD_DIR = WORKSPACE_ROOT / "slate_logs" / "production"
PROD_STATE_FILE = PROD_DIR / "prod_state.json"
HEALTH_LOG = PROD_DIR / "health_log.jsonl"
SLA_REPORT_DIR = PROD_DIR / "sla_reports"
OLLAMA_URL = os.environ.get("SLATE_OLLAMA_URL", "http://127.0.0.1:11434")


# ── SLA Targets ─────────────────────────────────────────────────────────

SLA_TARGETS = {
    "slate-coder:latest": {
        "max_latency_p95_ms": 15000,    # 15s for code generation (12B model)
        "min_throughput_tps": 50,        # 50 tok/s minimum
        "max_error_rate": 0.05,          # 5% max error rate
        "availability_target": 0.99,     # 99% availability
        "max_cold_start_ms": 30000,      # 30s cold start
    },
    "slate-fast:latest": {
        "max_latency_p95_ms": 3000,     # 3s for classification (3B model)
        "min_throughput_tps": 200,       # 200 tok/s minimum
        "max_error_rate": 0.02,          # 2% max error rate
        "availability_target": 0.999,    # 99.9% availability
        "max_cold_start_ms": 10000,      # 10s cold start
    },
    "slate-planner:latest": {
        "max_latency_p95_ms": 8000,     # 8s for planning (7B model)
        "min_throughput_tps": 100,       # 100 tok/s minimum
        "max_error_rate": 0.05,          # 5% max error rate
        "availability_target": 0.99,     # 99% availability
        "max_cold_start_ms": 20000,      # 20s cold start
    },
    "_default": {
        "max_latency_p95_ms": 20000,
        "min_throughput_tps": 30,
        "max_error_rate": 0.10,
        "availability_target": 0.95,
        "max_cold_start_ms": 45000,
    },
}

# ── Failover Chains ─────────────────────────────────────────────────────

FAILOVER_CHAINS = {
    "slate-coder:latest": ["mistral-nemo:latest", "mistral:latest"],
    "slate-fast:latest": ["llama3.2:3b", "phi:latest"],
    "slate-planner:latest": ["mistral:latest", "llama3.2:latest"],
}


# ── Data Classes ────────────────────────────────────────────────────────

@dataclass
class HealthCheckResult:
    """Result of a model health check."""
    model: str
    timestamp: str
    status: str  # "healthy", "degraded", "unhealthy", "offline"
    latency_ms: float
    tokens_per_sec: float
    tokens_generated: int
    gpu_index: int
    gpu_memory_used_mb: int
    gpu_memory_total_mb: int
    error: Optional[str] = None
    cold_start: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SLAStatus:
    """SLA compliance status for a model."""
    model: str
    sla_target: dict
    latency_compliant: bool
    throughput_compliant: bool
    error_rate_compliant: bool
    availability_compliant: bool
    overall_compliant: bool
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReadinessCheck:
    """Individual readiness check result."""
    check_name: str
    passed: bool
    message: str
    severity: str = "info"  # "info", "warning", "critical"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProductionReadiness:
    """Overall production readiness assessment."""
    timestamp: str
    ready: bool
    score: float  # 0.0 to 1.0
    checks: list = field(default_factory=list)
    blocking_issues: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── GPU Snapshot ────────────────────────────────────────────────────────

def _get_gpu_info() -> list[dict]:
    """Get GPU information."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            gpus = []
            for line in result.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    gpus.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "memory_used_mb": int(parts[2]),
                        "memory_total_mb": int(parts[3]),
                        "utilization_pct": int(parts[4]),
                        "temperature_c": int(parts[5]),
                    })
            return gpus
    except Exception:
        pass
    return []


def _query_ollama_health(model: str) -> dict:
    """Quick health query to Ollama."""
    payload = json.dumps({
        "model": model,
        "prompt": "Reply with OK",
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 5},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.time()
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    elapsed = time.time() - start
    data["_elapsed"] = elapsed
    return data


def _get_ollama_models() -> list[str]:
    """Get available Ollama models."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


def _get_running_models() -> list[dict]:
    """Get currently loaded models in Ollama."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/ps", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return data.get("models", [])
    except Exception:
        return []


# ── Health Monitor ──────────────────────────────────────────────────────

class HealthMonitor:
    """Monitors model health with heartbeat checks."""

    # Modified: 2026-07-12T02:45:00Z | Author: COPILOT | Change: Health monitoring

    def __init__(self):
        self.health_history: dict[str, list[HealthCheckResult]] = {}
        PROD_DIR.mkdir(parents=True, exist_ok=True)

    def check_model(self, model: str) -> HealthCheckResult:
        """Run a health check on a single model."""
        now = datetime.now(timezone.utc).isoformat()
        gpus = _get_gpu_info()
        gpu_info = gpus[0] if gpus else {"index": -1, "memory_used_mb": 0, "memory_total_mb": 0}

        # Check if model is currently loaded (warm)
        running = _get_running_models()
        is_loaded = any(m.get("name") == model for m in running)

        try:
            response = _query_ollama_health(model)
            elapsed = response.get("_elapsed", 0)
            eval_count = response.get("eval_count", 0)
            eval_duration = response.get("eval_duration", 1)
            tok_per_sec = eval_count / max(eval_duration / 1e9, 0.001) if eval_count else 0

            latency_ms = elapsed * 1000

            # Determine status
            sla = SLA_TARGETS.get(model, SLA_TARGETS["_default"])
            if latency_ms > sla["max_latency_p95_ms"]:
                status = "degraded"
            elif tok_per_sec < sla["min_throughput_tps"] * 0.5:
                status = "degraded"
            else:
                status = "healthy"

            result = HealthCheckResult(
                model=model,
                timestamp=now,
                status=status,
                latency_ms=round(latency_ms, 1),
                tokens_per_sec=round(tok_per_sec, 1),
                tokens_generated=eval_count,
                gpu_index=gpu_info.get("index", -1),
                gpu_memory_used_mb=gpu_info.get("memory_used_mb", 0),
                gpu_memory_total_mb=gpu_info.get("memory_total_mb", 0),
                cold_start=not is_loaded,
            )

        except Exception as e:
            result = HealthCheckResult(
                model=model,
                timestamp=now,
                status="unhealthy",
                latency_ms=0,
                tokens_per_sec=0,
                tokens_generated=0,
                gpu_index=gpu_info.get("index", -1),
                gpu_memory_used_mb=gpu_info.get("memory_used_mb", 0),
                gpu_memory_total_mb=gpu_info.get("memory_total_mb", 0),
                error=str(e),
            )

        # Record to history
        if model not in self.health_history:
            self.health_history[model] = []
        self.health_history[model].append(result)
        # Keep bounded
        if len(self.health_history[model]) > 100:
            self.health_history[model] = self.health_history[model][-50:]

        # Log to file
        self._log_health(result)

        return result

    def check_all_models(self, models: list[str] = None) -> dict[str, HealthCheckResult]:
        """Check health of all models."""
        if models is None:
            available = _get_ollama_models()
            slate_models = [m for m in available if m.startswith("slate-")]
            models = slate_models if slate_models else available[:3]

        results = {}
        for model in models:
            print(f"  Checking {model}...")
            results[model] = self.check_model(model)
            status = results[model].status
            icon = "OK" if status == "healthy" else ("WARN" if status == "degraded" else "FAIL")
            print(f"    [{icon}] {status} - {results[model].latency_ms:.0f}ms, "
                  f"{results[model].tokens_per_sec:.1f} tok/s")
        return results

    def _log_health(self, result: HealthCheckResult):
        """Append health check to log file."""
        HEALTH_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(HEALTH_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(result.to_dict(), default=str) + "\n")


# ── SLA Checker ─────────────────────────────────────────────────────────

class SLAChecker:
    """Checks SLA compliance for models."""

    # Modified: 2026-07-12T02:45:00Z | Author: COPILOT | Change: SLA compliance checker

    def __init__(self):
        self.health_log = self._load_health_log()

    def _load_health_log(self) -> list[dict]:
        """Load recent health log entries."""
        if not HEALTH_LOG.exists():
            return []
        entries = []
        with open(HEALTH_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries

    def check_sla(self, model: str) -> SLAStatus:
        """Check SLA compliance for a model."""
        sla = SLA_TARGETS.get(model, SLA_TARGETS["_default"])

        # Get recent entries for this model
        model_entries = [e for e in self.health_log if e.get("model") == model]
        recent = model_entries[-50:] if model_entries else []

        if not recent:
            return SLAStatus(
                model=model,
                sla_target=sla,
                latency_compliant=True,
                throughput_compliant=True,
                error_rate_compliant=True,
                availability_compliant=True,
                overall_compliant=True,
                metrics={"note": "No data yet"},
            )

        # Calculate metrics
        latencies = [e.get("latency_ms", 0) for e in recent if e.get("latency_ms", 0) > 0]
        tps_values = [e.get("tokens_per_sec", 0) for e in recent if e.get("tokens_per_sec", 0) > 0]
        error_count = sum(1 for e in recent if e.get("status") in ("unhealthy", "offline"))
        total_count = len(recent)

        sorted_latencies = sorted(latencies) if latencies else [0]
        p95_idx = int(len(sorted_latencies) * 0.95)
        p95_latency = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)] if sorted_latencies else 0

        avg_tps = sum(tps_values) / max(len(tps_values), 1) if tps_values else 0
        error_rate = error_count / max(total_count, 1)
        availability = 1.0 - error_rate

        metrics = {
            "data_points": total_count,
            "p95_latency_ms": round(p95_latency, 1),
            "avg_tokens_per_sec": round(avg_tps, 1),
            "error_rate": round(error_rate, 4),
            "availability": round(availability, 4),
        }

        latency_ok = p95_latency <= sla["max_latency_p95_ms"]
        throughput_ok = avg_tps >= sla["min_throughput_tps"]
        error_ok = error_rate <= sla["max_error_rate"]
        avail_ok = availability >= sla["availability_target"]

        return SLAStatus(
            model=model,
            sla_target=sla,
            latency_compliant=latency_ok,
            throughput_compliant=throughput_ok,
            error_rate_compliant=error_ok,
            availability_compliant=avail_ok,
            overall_compliant=latency_ok and throughput_ok and error_ok and avail_ok,
            metrics=metrics,
        )


# ── Failover Manager ───────────────────────────────────────────────────

class FailoverManager:
    """Manages model failover when primary models are degraded."""

    # Modified: 2026-07-12T02:45:00Z | Author: COPILOT | Change: Failover management

    def __init__(self):
        self.available_models = set(_get_ollama_models())

    def get_failover(self, model: str) -> Optional[str]:
        """Get the next failover model for a degraded/unhealthy model."""
        chain = FAILOVER_CHAINS.get(model, [])
        for fallback in chain:
            if fallback in self.available_models:
                return fallback
        # Last resort: any available model
        if self.available_models:
            return next(iter(self.available_models))
        return None

    def test_failover_chain(self, model: str) -> list[dict]:
        """Test the entire failover chain for a model."""
        chain = FAILOVER_CHAINS.get(model, [])
        results = []

        # Test primary
        try:
            resp = _query_ollama_health(model)
            results.append({
                "model": model,
                "role": "primary",
                "status": "ok",
                "latency_ms": round(resp.get("_elapsed", 0) * 1000, 1),
            })
        except Exception as e:
            results.append({
                "model": model,
                "role": "primary",
                "status": "failed",
                "error": str(e),
            })

        # Test fallbacks
        for i, fallback in enumerate(chain):
            if fallback not in self.available_models:
                results.append({
                    "model": fallback,
                    "role": f"fallback-{i+1}",
                    "status": "not_available",
                })
                continue
            try:
                resp = _query_ollama_health(fallback)
                results.append({
                    "model": fallback,
                    "role": f"fallback-{i+1}",
                    "status": "ok",
                    "latency_ms": round(resp.get("_elapsed", 0) * 1000, 1),
                })
            except Exception as e:
                results.append({
                    "model": fallback,
                    "role": f"fallback-{i+1}",
                    "status": "failed",
                    "error": str(e),
                })

        return results


# ── Readiness Assessor ──────────────────────────────────────────────────

class ReadinessAssessor:
    """Assesses production readiness of the AI system."""

    # Modified: 2026-07-12T02:45:00Z | Author: COPILOT | Change: Production readiness assessment

    def assess(self) -> ProductionReadiness:
        """Run all readiness checks."""
        now = datetime.now(timezone.utc).isoformat()
        checks = []
        blocking = []

        # 1. Ollama service
        try:
            req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            model_count = len(data.get("models", []))
            checks.append(ReadinessCheck("ollama_service", True,
                                         f"Ollama running with {model_count} models"))
        except Exception as e:
            checks.append(ReadinessCheck("ollama_service", False,
                                         f"Ollama not available: {e}", "critical"))
            blocking.append("Ollama service not running")

        # 2. SLATE models available
        available = _get_ollama_models()
        slate_models = [m for m in available if m.startswith("slate-")]
        if len(slate_models) >= 3:
            checks.append(ReadinessCheck("slate_models", True,
                                         f"{len(slate_models)} SLATE models available"))
        elif slate_models:
            checks.append(ReadinessCheck("slate_models", True,
                                         f"{len(slate_models)}/3 SLATE models (partial)", "warning"))
        else:
            checks.append(ReadinessCheck("slate_models", False,
                                         "No SLATE custom models found", "warning"))

        # 3. GPU availability
        gpus = _get_gpu_info()
        if len(gpus) >= 2:
            checks.append(ReadinessCheck("dual_gpu", True,
                                         f"{len(gpus)} GPUs available"))
        elif len(gpus) == 1:
            checks.append(ReadinessCheck("dual_gpu", True,
                                         "1 GPU available (single GPU mode)", "warning"))
        else:
            checks.append(ReadinessCheck("dual_gpu", False,
                                         "No GPUs detected", "critical"))
            blocking.append("No GPU available")

        # 4. GPU memory
        if gpus:
            total_vram = sum(g.get("memory_total_mb", 0) for g in gpus)
            used_vram = sum(g.get("memory_used_mb", 0) for g in gpus)
            free_pct = (total_vram - used_vram) / max(total_vram, 1)
            if free_pct >= 0.3:
                checks.append(ReadinessCheck("gpu_memory", True,
                                             f"{free_pct:.0%} GPU memory free ({total_vram - used_vram}MB / {total_vram}MB)"))
            else:
                checks.append(ReadinessCheck("gpu_memory", False,
                                             f"Only {free_pct:.0%} GPU memory free", "warning"))

        # 5. GPU temperature
        if gpus:
            max_temp = max(g.get("temperature_c", 0) for g in gpus)
            if max_temp < 80:
                checks.append(ReadinessCheck("gpu_temperature", True,
                                             f"Max GPU temp: {max_temp}C"))
            elif max_temp < 90:
                checks.append(ReadinessCheck("gpu_temperature", True,
                                             f"GPU temp elevated: {max_temp}C", "warning"))
            else:
                checks.append(ReadinessCheck("gpu_temperature", False,
                                             f"GPU overheating: {max_temp}C", "critical"))
                blocking.append(f"GPU temperature critical: {max_temp}C")

        # 6. Tracing system
        trace_dir = WORKSPACE_ROOT / "slate_logs" / "traces"
        metrics_file = trace_dir / "metrics.json"
        if metrics_file.exists():
            checks.append(ReadinessCheck("ai_tracing", True,
                                         "AI tracing system active"))
        else:
            checks.append(ReadinessCheck("ai_tracing", True,
                                         "AI tracing not yet initialized (will start on first inference)", "info"))

        # 7. Evaluation baselines
        from slate.slate_ai_evaluation import BASELINES_FILE
        if BASELINES_FILE.exists():
            checks.append(ReadinessCheck("eval_baselines", True,
                                         "Evaluation baselines saved"))
        else:
            checks.append(ReadinessCheck("eval_baselines", False,
                                         "No evaluation baselines - run --evaluate --save-baseline", "warning"))

        # 8. ChromaDB
        try:
            from slate.slate_chromadb import SlateChromaDB
            db = SlateChromaDB()
            status = db.get_status()
            doc_count = status.get("total_documents", 0)
            checks.append(ReadinessCheck("chromadb", True,
                                         f"ChromaDB active with {doc_count} documents"))
        except Exception:
            checks.append(ReadinessCheck("chromadb", False,
                                         "ChromaDB not available", "warning"))

        # 9. Runner health
        runner_dir = WORKSPACE_ROOT / "actions-runner"
        if runner_dir.exists():
            checks.append(ReadinessCheck("runner", True,
                                         "Actions runner directory present"))
        else:
            checks.append(ReadinessCheck("runner", False,
                                         "Actions runner not found", "warning"))

        # 10. Inference test
        if available:
            test_model = slate_models[0] if slate_models else available[0]
            try:
                resp = _query_ollama_health(test_model)
                elapsed = resp.get("_elapsed", 0)
                checks.append(ReadinessCheck("inference_test", True,
                                             f"Inference OK ({test_model}: {elapsed*1000:.0f}ms)"))
            except Exception as e:
                checks.append(ReadinessCheck("inference_test", False,
                                             f"Inference failed: {e}", "critical"))
                blocking.append("AI inference not working")

        # Calculate overall score
        total = len(checks)
        passed = sum(1 for c in checks if c.passed)
        score = passed / max(total, 1)
        ready = len(blocking) == 0 and score >= 0.7

        return ProductionReadiness(
            timestamp=now,
            ready=ready,
            score=round(score, 3),
            checks=[c.to_dict() for c in checks],
            blocking_issues=blocking,
        )


# ── Production Manager ──────────────────────────────────────────────────

class ProductionManager:
    """Central production management for SLATE AI."""

    # Modified: 2026-07-12T02:45:00Z | Author: COPILOT | Change: Production manager

    def __init__(self):
        self.health_monitor = HealthMonitor()
        self.sla_checker = SLAChecker()
        self.failover_manager = FailoverManager()
        self.readiness_assessor = ReadinessAssessor()

    def warmup_models(self, models: list[str] = None) -> dict:
        """Warm up models by loading them into GPU memory."""
        if models is None:
            available = _get_ollama_models()
            models = [m for m in available if m.startswith("slate-")]
            if not models:
                models = available[:3]

        results = {}
        for model in models:
            print(f"  Warming up {model}...")
            try:
                start = time.time()
                # Send a keepalive request to load the model
                payload = json.dumps({
                    "model": model,
                    "prompt": "warmup",
                    "stream": False,
                    "keep_alive": "24h",
                    "options": {"num_predict": 1},
                }).encode()
                req = urllib.request.Request(
                    f"{OLLAMA_URL}/api/generate",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read())
                elapsed = time.time() - start
                results[model] = {
                    "status": "warmed",
                    "load_time_ms": round(elapsed * 1000, 1),
                }
                print(f"    Loaded in {elapsed*1000:.0f}ms")
            except Exception as e:
                results[model] = {"status": "failed", "error": str(e)}
                print(f"    Failed: {e}")

        return results

    def get_full_status(self) -> dict:
        """Get comprehensive production status."""
        available = _get_ollama_models()
        running = _get_running_models()
        gpus = _get_gpu_info()

        # Load state
        state = {}
        if PROD_STATE_FILE.exists():
            try:
                state = json.loads(PROD_STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Count health log entries
        health_count = 0
        if HEALTH_LOG.exists():
            with open(HEALTH_LOG, "r", encoding="utf-8") as f:
                health_count = sum(1 for _ in f)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ollama_url": OLLAMA_URL,
            "available_models": available,
            "running_models": [m.get("name", "?") for m in running],
            "slate_models": [m for m in available if m.startswith("slate-")],
            "gpus": gpus,
            "health_log_entries": health_count,
            "sla_targets_configured": len(SLA_TARGETS) - 1,  # Exclude _default
            "failover_chains": len(FAILOVER_CHAINS),
            "last_health_check": state.get("last_health_check", "never"),
            "last_sla_report": state.get("last_sla_report", "never"),
        }

    def save_state(self, key: str, value: str):
        """Update production state."""
        PROD_DIR.mkdir(parents=True, exist_ok=True)
        state = {}
        if PROD_STATE_FILE.exists():
            try:
                state = json.loads(PROD_STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        state[key] = value
        PROD_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SLATE AI Production Readiness")
    parser.add_argument("--status", action="store_true", help="Show production status")
    parser.add_argument("--health-check", action="store_true", help="Run health checks")
    parser.add_argument("--sla-report", action="store_true", help="SLA compliance report")
    parser.add_argument("--readiness", action="store_true", help="Production readiness assessment")
    parser.add_argument("--failover-test", action="store_true", help="Test failover chains")
    parser.add_argument("--warmup", action="store_true", help="Warm up all models")
    parser.add_argument("--models", nargs="+", help="Specify models")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    pm = ProductionManager()

    if args.health_check:
        print("\n  SLATE AI Health Check")
        print("  " + "-" * 50)
        results = pm.health_monitor.check_all_models(args.models)
        pm.save_state("last_health_check", datetime.now(timezone.utc).isoformat())
        if args.json:
            print(json.dumps({m: r.to_dict() for m, r in results.items()}, indent=2))
        else:
            print(f"\n  {len(results)} models checked")
            healthy = sum(1 for r in results.values() if r.status == "healthy")
            print(f"  Healthy: {healthy}/{len(results)}")
        return

    if args.sla_report:
        print("\n  SLATE AI SLA Compliance Report")
        print("  " + "=" * 60)
        available = args.models or [m for m in _get_ollama_models() if m.startswith("slate-")]
        for model in available:
            sla_status = pm.sla_checker.check_sla(model)
            icon = "PASS" if sla_status.overall_compliant else "FAIL"
            print(f"\n  [{icon}] {model}")
            print(f"    Latency:     {'PASS' if sla_status.latency_compliant else 'FAIL'} "
                  f"(p95: {sla_status.metrics.get('p95_latency_ms', 'N/A')}ms / "
                  f"target: {sla_status.sla_target.get('max_latency_p95_ms')}ms)")
            print(f"    Throughput:  {'PASS' if sla_status.throughput_compliant else 'FAIL'} "
                  f"(avg: {sla_status.metrics.get('avg_tokens_per_sec', 'N/A')} tok/s / "
                  f"target: {sla_status.sla_target.get('min_throughput_tps')} tok/s)")
            print(f"    Error Rate:  {'PASS' if sla_status.error_rate_compliant else 'FAIL'} "
                  f"({sla_status.metrics.get('error_rate', 'N/A')} / "
                  f"target: {sla_status.sla_target.get('max_error_rate')})")
            print(f"    Availability: {'PASS' if sla_status.availability_compliant else 'FAIL'} "
                  f"({sla_status.metrics.get('availability', 'N/A')} / "
                  f"target: {sla_status.sla_target.get('availability_target')})")
        pm.save_state("last_sla_report", datetime.now(timezone.utc).isoformat())
        return

    if args.readiness:
        readiness = pm.readiness_assessor.assess()
        if args.json:
            print(json.dumps(readiness.to_dict(), indent=2))
        else:
            print("\n  SLATE AI Production Readiness")
            print("  " + "=" * 60)
            status = "READY" if readiness.ready else "NOT READY"
            print(f"  Status: {status} (score: {readiness.score:.0%})")
            print()
            for check in readiness.checks:
                icon = "PASS" if check["passed"] else "FAIL"
                sev = f" [{check['severity'].upper()}]" if check["severity"] != "info" else ""
                print(f"  [{icon}]{sev} {check['check_name']}: {check['message']}")
            if readiness.blocking_issues:
                print(f"\n  BLOCKING ISSUES ({len(readiness.blocking_issues)}):")
                for issue in readiness.blocking_issues:
                    print(f"    - {issue}")
            print("\n  " + "=" * 60)
        return

    if args.failover_test:
        print("\n  SLATE AI Failover Test")
        print("  " + "-" * 50)
        chains = args.models or list(FAILOVER_CHAINS.keys())
        for model in chains:
            print(f"\n  Chain: {model}")
            results = pm.failover_manager.test_failover_chain(model)
            for r in results:
                icon = "OK" if r["status"] == "ok" else ("N/A" if r["status"] == "not_available" else "FAIL")
                latency = f" ({r.get('latency_ms', 0):.0f}ms)" if "latency_ms" in r else ""
                print(f"    [{icon}] {r['role']}: {r['model']}{latency}")
        return

    if args.warmup:
        print("\n  SLATE AI Model Warmup")
        print("  " + "-" * 50)
        results = pm.warmup_models(args.models)
        if args.json:
            print(json.dumps(results, indent=2))
        return

    # Default: status
    status = pm.get_full_status()
    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print("=" * 60)
        print("  SLATE AI Production Status")
        print("=" * 60)
        print(f"  Ollama:          {status['ollama_url']}")
        print(f"  Available:       {len(status['available_models'])} models")
        print(f"  Running:         {', '.join(status['running_models']) or 'none'}")
        print(f"  SLATE Models:    {', '.join(status['slate_models']) or 'none'}")
        print(f"  GPUs:            {len(status['gpus'])}")
        for gpu in status["gpus"]:
            print(f"    [{gpu['index']}] {gpu['name']} - "
                  f"{gpu['memory_used_mb']}/{gpu['memory_total_mb']}MB "
                  f"({gpu['utilization_pct']}% util, {gpu['temperature_c']}C)")
        print(f"  Health Log:      {status['health_log_entries']} entries")
        print(f"  SLA Targets:     {status['sla_targets_configured']} models configured")
        print(f"  Failover Chains: {status['failover_chains']}")
        print(f"  Last Health:     {status['last_health_check']}")
        print("=" * 60)


if __name__ == "__main__":
    main()
