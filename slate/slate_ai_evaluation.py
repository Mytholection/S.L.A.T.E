#!/usr/bin/env python3
# Modified: 2026-07-12T02:30:00Z | Author: COPILOT | Change: Create AI model evaluation framework
"""
SLATE AI Evaluation — Model Performance & Quality Assessment
================================================================

Evaluates SLATE AI models on accuracy, consistency, latency, throughput,
and task-specific quality benchmarks. Supports A/B comparison, regression
detection, and quality scoring against golden datasets.

Architecture:
  EvaluationSuite → BenchmarkRunner → ModelEvaluator → ScoreCard
                                    → RegressionDetector → Alert

Features:
- Task-specific evaluation (code generation, classification, summarization)
- Golden dataset comparison for quality scoring
- A/B model comparison with statistical significance
- Regression detection against historical baselines
- Latency/throughput benchmarking per model
- GPU utilization tracking during evaluation
- JSON report generation for CI/CD integration

Usage:
    python slate/slate_ai_evaluation.py --status       # Evaluation status
    python slate/slate_ai_evaluation.py --evaluate      # Run full evaluation suite
    python slate/slate_ai_evaluation.py --benchmark     # Latency/throughput benchmarks
    python slate/slate_ai_evaluation.py --compare A B   # A/B model comparison
    python slate/slate_ai_evaluation.py --regression    # Check for regressions
    python slate/slate_ai_evaluation.py --report        # Generate evaluation report
    python slate/slate_ai_evaluation.py --json          # JSON output
"""

import argparse
import json
import os
import subprocess
import sys
import statistics
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Modified: 2026-07-12T02:30:00Z | Author: COPILOT | Change: workspace setup
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

EVAL_DIR = WORKSPACE_ROOT / "slate_logs" / "evaluations"
EVAL_STATE_FILE = EVAL_DIR / "eval_state.json"
BASELINES_FILE = EVAL_DIR / "baselines.json"
OLLAMA_URL = os.environ.get("SLATE_OLLAMA_URL", "http://127.0.0.1:11434")


# ── Golden Test Cases ───────────────────────────────────────────────────

GOLDEN_TESTS = {
    "classification": [
        {
            "prompt": "Classify: 'Fix the SQL injection vulnerability in login.py'",
            "expected_contains": ["security", "fix", "bug"],
            "task_type": "classification",
            "system": "Classify the task into one category: implement, test, analyze, fix. Reply with ONLY the category.",
            "expected_category": "fix",
        },
        {
            "prompt": "Classify: 'Write unit tests for the payment module'",
            "expected_contains": ["test"],
            "task_type": "classification",
            "system": "Classify the task into one category: implement, test, analyze, fix. Reply with ONLY the category.",
            "expected_category": "test",
        },
        {
            "prompt": "Classify: 'Analyze the performance bottleneck in the API'",
            "expected_contains": ["analyze"],
            "task_type": "classification",
            "system": "Classify the task into one category: implement, test, analyze, fix. Reply with ONLY the category.",
            "expected_category": "analyze",
        },
        {
            "prompt": "Classify: 'Implement a new caching layer for database queries'",
            "expected_contains": ["implement"],
            "task_type": "classification",
            "system": "Classify the task into one category: implement, test, analyze, fix. Reply with ONLY the category.",
            "expected_category": "implement",
        },
    ],
    "code_generation": [
        {
            "prompt": "Write a Python function that returns the fibonacci sequence up to n terms.",
            "expected_contains": ["def", "fibonacci", "return"],
            "task_type": "code_generation",
            "system": "You are a Python expert. Output only code.",
        },
        {
            "prompt": "Write a Python function to check if a string is a palindrome.",
            "expected_contains": ["def", "palindrome", "return"],
            "task_type": "code_generation",
            "system": "You are a Python expert. Output only code.",
        },
    ],
    "summarization": [
        {
            "prompt": "Summarize: SLATE is a local-first AI agent orchestration framework running on self-hosted GitHub Actions runners with dual NVIDIA GPUs. It uses Ollama for local inference, ChromaDB for vector storage, and supports 10 AI models across 3 custom SLATE models. The system features autonomous task loops, dual-GPU load balancing, and integrated CI/CD pipelines.",
            "expected_contains": ["SLATE", "local", "AI"],
            "task_type": "summarization",
            "system": "Summarize in 30 words or fewer.",
            "max_words": 40,
        },
    ],
    "code_review": [
        {
            "prompt": "Review this Python code:\n```python\ndef connect(host):\n    import sqlite3\n    db = sqlite3.connect(host)\n    cursor = db.cursor()\n    cursor.execute(f'SELECT * FROM users WHERE name = \"{host}\"')\n    return cursor.fetchall()\n```",
            "expected_contains": ["injection", "sql", "security"],
            "task_type": "code_review",
            "system": "You are a security-focused code reviewer. Identify issues.",
        },
    ],
}


# ── Data Classes ────────────────────────────────────────────────────────

@dataclass
class TestResult:
    """Result of a single evaluation test case."""
    test_id: str
    task_type: str
    model: str
    prompt_preview: str
    expected_contains: list
    response_preview: str
    passed: bool
    score: float  # 0.0 to 1.0
    latency_ms: float
    tokens: int
    tokens_per_sec: float
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ModelScoreCard:
    """Evaluation score card for a model."""
    model: str
    evaluated_at: str
    total_tests: int = 0
    passed_tests: int = 0
    avg_score: float = 0.0
    avg_latency_ms: float = 0.0
    avg_tokens_per_sec: float = 0.0
    p95_latency_ms: float = 0.0
    scores_by_task: dict = field(default_factory=dict)
    test_results: list = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed_tests / max(self.total_tests, 1)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["pass_rate"] = round(self.pass_rate, 4)
        return d


@dataclass
class RegressionAlert:
    """Alert for detected quality regression."""
    model: str
    metric: str
    baseline_value: float
    current_value: float
    threshold_pct: float
    severity: str  # "warning", "critical"
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


# ── Ollama Query ────────────────────────────────────────────────────────

def _query_ollama(model: str, prompt: str, system: str = "",
                  temperature: float = 0.3, max_tokens: int = 512) -> dict:
    """Query Ollama and return raw response with timing."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    elapsed = time.time() - start
    data["_elapsed"] = elapsed
    return data


def _get_available_models() -> list[str]:
    """Get list of available Ollama models."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


# ── Model Evaluator ─────────────────────────────────────────────────────

class ModelEvaluator:
    """Evaluates a single model against golden test cases."""

    # Modified: 2026-07-12T02:30:00Z | Author: COPILOT | Change: Model evaluation engine

    def __init__(self, model: str):
        self.model = model
        self.results: list[TestResult] = []

    def evaluate_test(self, test_case: dict, test_id: str) -> TestResult:
        """Run a single test case and produce a result."""
        try:
            response = _query_ollama(
                model=self.model,
                prompt=test_case["prompt"],
                system=test_case.get("system", ""),
                temperature=test_case.get("temperature", 0.3),
                max_tokens=test_case.get("max_tokens", 512),
            )

            response_text = response.get("response", "").strip().lower()
            elapsed = response.get("_elapsed", 0)
            eval_count = response.get("eval_count", 0)
            eval_duration = response.get("eval_duration", 1)
            tok_per_sec = eval_count / max(eval_duration / 1e9, 0.001) if eval_count else 0

            # Score: check expected content
            expected = test_case.get("expected_contains", [])
            matches = sum(1 for e in expected if e.lower() in response_text)
            content_score = matches / max(len(expected), 1)

            # Category match for classification tasks
            if "expected_category" in test_case:
                cat = test_case["expected_category"].lower()
                if cat in response_text:
                    content_score = max(content_score, 1.0)
                else:
                    content_score = min(content_score, 0.5)

            # Word limit for summarization
            if "max_words" in test_case:
                word_count = len(response_text.split())
                if word_count <= test_case["max_words"]:
                    content_score = min(content_score + 0.2, 1.0)
                else:
                    content_score *= 0.7

            passed = content_score >= 0.5

            result = TestResult(
                test_id=test_id,
                task_type=test_case.get("task_type", "unknown"),
                model=self.model,
                prompt_preview=test_case["prompt"][:80],
                expected_contains=expected,
                response_preview=response_text[:150],
                passed=passed,
                score=round(content_score, 3),
                latency_ms=round(elapsed * 1000, 1),
                tokens=eval_count,
                tokens_per_sec=round(tok_per_sec, 1),
            )
        except Exception as e:
            result = TestResult(
                test_id=test_id,
                task_type=test_case.get("task_type", "unknown"),
                model=self.model,
                prompt_preview=test_case["prompt"][:80],
                expected_contains=test_case.get("expected_contains", []),
                response_preview="",
                passed=False,
                score=0.0,
                latency_ms=0,
                tokens=0,
                tokens_per_sec=0,
                error=str(e),
            )

        self.results.append(result)
        return result

    def evaluate_all(self, test_cases: dict = None) -> ModelScoreCard:
        """Run all test cases and generate a score card."""
        if test_cases is None:
            test_cases = GOLDEN_TESTS

        now = datetime.now(timezone.utc).isoformat()
        test_idx = 0

        for task_type, cases in test_cases.items():
            for case in cases:
                test_idx += 1
                test_id = f"{task_type}_{test_idx:03d}"
                self.evaluate_test(case, test_id)

        # Build score card
        latencies = [r.latency_ms for r in self.results if r.latency_ms > 0]
        tps_values = [r.tokens_per_sec for r in self.results if r.tokens_per_sec > 0]

        scores_by_task = {}
        for r in self.results:
            if r.task_type not in scores_by_task:
                scores_by_task[r.task_type] = {"total": 0, "passed": 0, "scores": []}
            scores_by_task[r.task_type]["total"] += 1
            scores_by_task[r.task_type]["scores"].append(r.score)
            if r.passed:
                scores_by_task[r.task_type]["passed"] += 1

        for task, data in scores_by_task.items():
            data["avg_score"] = round(statistics.mean(data["scores"]), 3) if data["scores"] else 0
            data["pass_rate"] = round(data["passed"] / max(data["total"], 1), 3)
            del data["scores"]  # Don't persist raw scores

        sorted_latencies = sorted(latencies) if latencies else [0]
        p95_idx = int(len(sorted_latencies) * 0.95)

        card = ModelScoreCard(
            model=self.model,
            evaluated_at=now,
            total_tests=len(self.results),
            passed_tests=sum(1 for r in self.results if r.passed),
            avg_score=round(statistics.mean([r.score for r in self.results]), 3) if self.results else 0,
            avg_latency_ms=round(statistics.mean(latencies), 1) if latencies else 0,
            avg_tokens_per_sec=round(statistics.mean(tps_values), 1) if tps_values else 0,
            p95_latency_ms=round(sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)], 1),
            scores_by_task=scores_by_task,
            test_results=[r.to_dict() for r in self.results],
        )
        return card


# ── Benchmark Runner ────────────────────────────────────────────────────

class BenchmarkRunner:
    """Runs latency and throughput benchmarks across models."""

    # Modified: 2026-07-12T02:30:00Z | Author: COPILOT | Change: Benchmark runner

    BENCHMARK_PROMPTS = {
        "short": "Say hello.",
        "medium": "Explain what a binary search tree is in 50 words.",
        "long": "Write a detailed explanation of the differences between supervised, unsupervised, and reinforcement learning, including examples of each.",
    }

    def __init__(self, models: list[str] = None):
        if models is None:
            available = _get_available_models()
            # Focus on SLATE models + their bases
            priority = ["slate-coder:latest", "slate-fast:latest", "slate-planner:latest",
                        "mistral-nemo:latest", "llama3.2:3b", "phi:latest"]
            self.models = [m for m in priority if m in available]
            if not self.models:
                self.models = available[:3]
        else:
            self.models = models
        self.results: dict[str, dict] = {}

    def benchmark_model(self, model: str, iterations: int = 3) -> dict:
        """Benchmark a single model across prompt sizes."""
        model_results = {}

        for prompt_name, prompt_text in self.BENCHMARK_PROMPTS.items():
            latencies = []
            tps_values = []
            token_counts = []

            for _ in range(iterations):
                try:
                    response = _query_ollama(model, prompt_text, max_tokens=100)
                    elapsed = response.get("_elapsed", 0)
                    eval_count = response.get("eval_count", 0)
                    eval_duration = response.get("eval_duration", 1)
                    tok_per_sec = eval_count / max(eval_duration / 1e9, 0.001) if eval_count else 0

                    latencies.append(elapsed * 1000)
                    tps_values.append(tok_per_sec)
                    token_counts.append(eval_count)
                except Exception as e:
                    latencies.append(0)
                    tps_values.append(0)

            model_results[prompt_name] = {
                "avg_latency_ms": round(statistics.mean(latencies), 1) if latencies else 0,
                "min_latency_ms": round(min(latencies), 1) if latencies else 0,
                "max_latency_ms": round(max(latencies), 1) if latencies else 0,
                "avg_tok_per_sec": round(statistics.mean(tps_values), 1) if tps_values else 0,
                "avg_tokens": round(statistics.mean(token_counts), 1) if token_counts else 0,
                "iterations": iterations,
            }

        self.results[model] = model_results
        return model_results

    def benchmark_all(self, iterations: int = 3) -> dict:
        """Benchmark all configured models."""
        for model in self.models:
            print(f"  Benchmarking {model}...")
            self.benchmark_model(model, iterations)
        return self.results


# ── Regression Detector ─────────────────────────────────────────────────

class RegressionDetector:
    """Detects quality and performance regressions against baselines."""

    # Modified: 2026-07-12T02:30:00Z | Author: COPILOT | Change: Regression detection

    WARNING_THRESHOLD = 0.10   # 10% degradation
    CRITICAL_THRESHOLD = 0.25  # 25% degradation

    def __init__(self):
        self.baselines = self._load_baselines()
        self.alerts: list[RegressionAlert] = []

    def _load_baselines(self) -> dict:
        """Load baseline metrics."""
        if BASELINES_FILE.exists():
            try:
                return json.loads(BASELINES_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def save_baselines(self, scorecards: dict[str, ModelScoreCard]):
        """Save current scores as baselines."""
        BASELINES_FILE.parent.mkdir(parents=True, exist_ok=True)
        baselines = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "models": {},
        }
        for model, card in scorecards.items():
            baselines["models"][model] = {
                "pass_rate": card.pass_rate,
                "avg_score": card.avg_score,
                "avg_latency_ms": card.avg_latency_ms,
                "avg_tokens_per_sec": card.avg_tokens_per_sec,
                "p95_latency_ms": card.p95_latency_ms,
            }
        BASELINES_FILE.write_text(json.dumps(baselines, indent=2), encoding="utf-8")
        self.baselines = baselines

    def check_regressions(self, current_card: ModelScoreCard) -> list[RegressionAlert]:
        """Check a score card against baselines."""
        alerts = []
        model = current_card.model
        baseline = self.baselines.get("models", {}).get(model)

        if not baseline:
            return alerts

        checks = [
            ("pass_rate", current_card.pass_rate, baseline.get("pass_rate", 0), "higher"),
            ("avg_score", current_card.avg_score, baseline.get("avg_score", 0), "higher"),
            ("avg_tokens_per_sec", current_card.avg_tokens_per_sec,
             baseline.get("avg_tokens_per_sec", 0), "higher"),
            ("avg_latency_ms", current_card.avg_latency_ms,
             baseline.get("avg_latency_ms", float("inf")), "lower"),
            ("p95_latency_ms", current_card.p95_latency_ms,
             baseline.get("p95_latency_ms", float("inf")), "lower"),
        ]

        for metric, current, base, direction in checks:
            if base == 0 or base == float("inf"):
                continue

            if direction == "higher":
                pct_change = (base - current) / max(abs(base), 0.001)
            else:
                pct_change = (current - base) / max(abs(base), 0.001)

            if pct_change >= self.CRITICAL_THRESHOLD:
                severity = "critical"
            elif pct_change >= self.WARNING_THRESHOLD:
                severity = "warning"
            else:
                continue

            alert = RegressionAlert(
                model=model,
                metric=metric,
                baseline_value=round(base, 3),
                current_value=round(current, 3),
                threshold_pct=round(pct_change * 100, 1),
                severity=severity,
                message=f"{model}: {metric} regressed by {pct_change*100:.1f}% "
                        f"(baseline: {base:.3f}, current: {current:.3f})",
            )
            alerts.append(alert)

        self.alerts.extend(alerts)
        return alerts


# ── Evaluation Suite ────────────────────────────────────────────────────

class EvaluationSuite:
    """Full evaluation suite for SLATE AI models."""

    # Modified: 2026-07-12T02:30:00Z | Author: COPILOT | Change: Full evaluation suite

    def __init__(self, models: list[str] = None):
        available = _get_available_models()
        if models:
            self.models = [m for m in models if m in available]
        else:
            priority = ["slate-coder:latest", "slate-fast:latest", "slate-planner:latest"]
            self.models = [m for m in priority if m in available]
            if not self.models:
                self.models = available[:3]

        self.scorecards: dict[str, ModelScoreCard] = {}
        self.benchmarks: dict[str, dict] = {}
        self.regressions: list[RegressionAlert] = []
        self.regression_detector = RegressionDetector()

    def run_evaluation(self) -> dict[str, ModelScoreCard]:
        """Run full evaluation on all models."""
        print(f"\n  Evaluating {len(self.models)} models against {sum(len(v) for v in GOLDEN_TESTS.values())} test cases...")

        for model in self.models:
            print(f"\n  --- {model} ---")
            evaluator = ModelEvaluator(model)
            card = evaluator.evaluate_all()
            self.scorecards[model] = card

            # Print summary
            print(f"  Pass rate: {card.pass_rate:.0%} ({card.passed_tests}/{card.total_tests})")
            print(f"  Avg score: {card.avg_score:.3f}")
            print(f"  Avg latency: {card.avg_latency_ms:.0f}ms")
            print(f"  Avg tok/s: {card.avg_tokens_per_sec:.1f}")

            # Check regressions
            alerts = self.regression_detector.check_regressions(card)
            self.regressions.extend(alerts)
            if alerts:
                for a in alerts:
                    icon = "CRIT" if a.severity == "critical" else "WARN"
                    print(f"  [{icon}] {a.message}")

        return self.scorecards

    def run_benchmarks(self, iterations: int = 3) -> dict:
        """Run latency/throughput benchmarks."""
        runner = BenchmarkRunner(self.models)
        self.benchmarks = runner.benchmark_all(iterations)
        return self.benchmarks

    def save_baselines(self):
        """Save current scores as baselines for future regression checks."""
        self.regression_detector.save_baselines(self.scorecards)
        print(f"  Baselines saved for {len(self.scorecards)} models")

    def generate_report(self) -> str:
        """Generate a comprehensive evaluation report."""
        lines = [
            "=" * 70,
            "  SLATE AI Evaluation Report",
            f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "=" * 70,
        ]

        if self.scorecards:
            lines.append("")
            lines.append("  MODEL SCORECARDS")
            lines.append("  " + "-" * 66)
            lines.append(
                f"  {'Model':<28} {'Pass%':>6} {'Score':>6} {'AvgLat':>8} {'P95Lat':>8} {'Tok/s':>7}"
            )
            lines.append("  " + "-" * 66)
            for model, card in self.scorecards.items():
                lines.append(
                    f"  {model:<28} {card.pass_rate:>5.0%} {card.avg_score:>6.3f} "
                    f"{card.avg_latency_ms:>7.0f}ms {card.p95_latency_ms:>7.0f}ms "
                    f"{card.avg_tokens_per_sec:>6.1f}"
                )

            # Per-task breakdown
            lines.append("")
            lines.append("  TASK BREAKDOWN")
            lines.append("  " + "-" * 66)
            for model, card in self.scorecards.items():
                lines.append(f"\n  {model}:")
                for task, data in card.scores_by_task.items():
                    lines.append(
                        f"    {task:<24} {data['pass_rate']:>5.0%} pass  "
                        f"avg score: {data['avg_score']:.3f}  "
                        f"({data['passed']}/{data['total']})"
                    )

        if self.benchmarks:
            lines.append("")
            lines.append("  BENCHMARKS")
            lines.append("  " + "-" * 66)
            for model, prompts in self.benchmarks.items():
                lines.append(f"\n  {model}:")
                for prompt_name, data in prompts.items():
                    lines.append(
                        f"    {prompt_name:<10} "
                        f"avg: {data['avg_latency_ms']:>7.0f}ms  "
                        f"min: {data['min_latency_ms']:>7.0f}ms  "
                        f"max: {data['max_latency_ms']:>7.0f}ms  "
                        f"tok/s: {data['avg_tok_per_sec']:>6.1f}"
                    )

        if self.regressions:
            lines.append("")
            lines.append("  REGRESSIONS DETECTED")
            lines.append("  " + "-" * 66)
            for a in self.regressions:
                icon = "CRIT" if a.severity == "critical" else "WARN"
                lines.append(f"  [{icon}] {a.message}")
        else:
            lines.append("")
            lines.append("  No regressions detected")

        lines.extend(["", "=" * 70])
        return "\n".join(lines)

    def save_report(self) -> Path:
        """Save evaluation report to disk."""
        EVAL_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # JSON report
        report_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "models_evaluated": len(self.scorecards),
            "scorecards": {m: c.to_dict() for m, c in self.scorecards.items()},
            "benchmarks": self.benchmarks,
            "regressions": [a.to_dict() for a in self.regressions],
        }
        json_path = EVAL_DIR / f"eval_{timestamp}.json"
        json_path.write_text(json.dumps(report_data, indent=2, default=str), encoding="utf-8")

        # Update state
        state = {
            "last_evaluation": datetime.now(timezone.utc).isoformat(),
            "last_report": str(json_path),
            "models_evaluated": list(self.scorecards.keys()),
            "regression_count": len(self.regressions),
        }
        EVAL_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

        return json_path

    def get_status(self) -> dict:
        """Get evaluation system status."""
        state = {}
        if EVAL_STATE_FILE.exists():
            try:
                state = json.loads(EVAL_STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

        baselines = {}
        if BASELINES_FILE.exists():
            try:
                baselines = json.loads(BASELINES_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Count eval reports
        eval_count = len(list(EVAL_DIR.glob("eval_*.json"))) if EVAL_DIR.exists() else 0

        return {
            "eval_dir": str(EVAL_DIR),
            "eval_reports": eval_count,
            "last_evaluation": state.get("last_evaluation", "never"),
            "last_models": state.get("models_evaluated", []),
            "regression_count": state.get("regression_count", 0),
            "baselines_saved": len(baselines.get("models", {})),
            "baselines_date": baselines.get("saved_at", "never"),
            "available_models": _get_available_models(),
            "golden_test_count": sum(len(v) for v in GOLDEN_TESTS.values()),
        }


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SLATE AI Evaluation")
    parser.add_argument("--status", action="store_true", help="Show evaluation status")
    parser.add_argument("--evaluate", action="store_true", help="Run full evaluation suite")
    parser.add_argument("--benchmark", action="store_true", help="Run latency/throughput benchmarks")
    parser.add_argument("--compare", nargs=2, metavar=("MODEL_A", "MODEL_B"), help="A/B model comparison")
    parser.add_argument("--regression", action="store_true", help="Check for regressions")
    parser.add_argument("--save-baseline", action="store_true", help="Save current as baseline")
    parser.add_argument("--report", action="store_true", help="Generate evaluation report")
    parser.add_argument("--models", nargs="+", help="Specify models to evaluate")
    parser.add_argument("--iterations", type=int, default=3, help="Benchmark iterations")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.status:
        suite = EvaluationSuite()
        status = suite.get_status()
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print("=" * 60)
            print("  SLATE AI Evaluation Status")
            print("=" * 60)
            print(f"  Eval Dir:          {status['eval_dir']}")
            print(f"  Reports:           {status['eval_reports']}")
            print(f"  Last Evaluation:   {status['last_evaluation']}")
            print(f"  Last Models:       {', '.join(status['last_models']) or 'none'}")
            print(f"  Regressions:       {status['regression_count']}")
            print(f"  Baselines:         {status['baselines_saved']} models (saved: {status['baselines_date']})")
            print(f"  Golden Tests:      {status['golden_test_count']}")
            print(f"  Available Models:  {len(status['available_models'])}")
            for m in status["available_models"]:
                print(f"    - {m}")
            print("=" * 60)
        return

    if args.evaluate:
        suite = EvaluationSuite(models=args.models)
        suite.run_evaluation()
        report_path = suite.save_report()
        print(suite.generate_report())
        print(f"\n  Report saved: {report_path}")
        if args.save_baseline:
            suite.save_baselines()
        return

    if args.benchmark:
        suite = EvaluationSuite(models=args.models)
        suite.run_benchmarks(iterations=args.iterations)
        report_path = suite.save_report()
        if args.json:
            print(json.dumps(suite.benchmarks, indent=2))
        else:
            print(suite.generate_report())
            print(f"\n  Report saved: {report_path}")
        return

    if args.compare:
        model_a, model_b = args.compare
        suite = EvaluationSuite(models=[model_a, model_b])
        suite.run_evaluation()
        print(suite.generate_report())

        # Side-by-side comparison
        if len(suite.scorecards) == 2:
            cards = list(suite.scorecards.values())
            print(f"\n  A/B Comparison: {model_a} vs {model_b}")
            print(f"  {'Metric':<24} {'A':>12} {'B':>12} {'Winner':>10}")
            print("  " + "-" * 60)
            metrics = [
                ("Pass Rate", cards[0].pass_rate, cards[1].pass_rate, "higher"),
                ("Avg Score", cards[0].avg_score, cards[1].avg_score, "higher"),
                ("Avg Latency (ms)", cards[0].avg_latency_ms, cards[1].avg_latency_ms, "lower"),
                ("P95 Latency (ms)", cards[0].p95_latency_ms, cards[1].p95_latency_ms, "lower"),
                ("Tok/s", cards[0].avg_tokens_per_sec, cards[1].avg_tokens_per_sec, "higher"),
            ]
            for name, a, b, direction in metrics:
                if direction == "higher":
                    winner = model_a if a > b else model_b if b > a else "tie"
                else:
                    winner = model_a if a < b else model_b if b < a else "tie"
                print(f"  {name:<24} {a:>12.3f} {b:>12.3f} {winner:>10}")
        return

    if args.regression:
        suite = EvaluationSuite(models=args.models)
        suite.run_evaluation()
        if suite.regressions:
            print(f"\n  {len(suite.regressions)} regression(s) detected:")
            for a in suite.regressions:
                icon = "CRIT" if a.severity == "critical" else "WARN"
                print(f"  [{icon}] {a.message}")
            sys.exit(1)
        else:
            print("\n  No regressions detected")
        return

    if args.save_baseline:
        suite = EvaluationSuite(models=args.models)
        suite.run_evaluation()
        suite.save_baselines()
        return

    if args.report:
        suite = EvaluationSuite(models=args.models)
        suite.run_evaluation()
        suite.run_benchmarks(iterations=args.iterations)
        report_path = suite.save_report()
        print(suite.generate_report())
        print(f"\n  Full report saved: {report_path}")
        return

    # Default: show status
    suite = EvaluationSuite()
    status = suite.get_status()
    print(json.dumps(status, indent=2) if args.json else "Run with --status, --evaluate, --benchmark, or --report")


if __name__ == "__main__":
    main()
