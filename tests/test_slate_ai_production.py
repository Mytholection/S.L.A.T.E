# Modified: 2026-07-12T02:50:00Z | Author: COPILOT | Change: Create tests for AI production module
"""
Tests for slate/slate_ai_production.py — model health monitoring,
SLA compliance, failover chains, production readiness.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from slate.slate_ai_production import (
    SLA_TARGETS,
    FAILOVER_CHAINS,
    PROD_DIR,
    OLLAMA_URL,
    HealthCheckResult,
    SLAStatus,
    ReadinessCheck,
    ProductionReadiness,
    HealthMonitor,
    SLAChecker,
    FailoverManager,
    ReadinessAssessor,
    ProductionManager,
    _get_gpu_info,
    _get_ollama_models,
    _get_running_models,
)


# ── Constants ───────────────────────────────────────────────────────────


class TestConstants:
    """Tests for production constants."""

    def test_sla_targets_slate_models(self):
        assert "slate-coder:latest" in SLA_TARGETS
        assert "slate-fast:latest" in SLA_TARGETS
        assert "slate-planner:latest" in SLA_TARGETS

    def test_sla_targets_have_default(self):
        assert "_default" in SLA_TARGETS

    def test_sla_targets_have_required_keys(self):
        required = ["max_latency_p95_ms", "min_throughput_tps",
                     "max_error_rate", "availability_target", "max_cold_start_ms"]
        for model, sla in SLA_TARGETS.items():
            for key in required:
                assert key in sla, f"{model} missing SLA key: {key}"

    def test_sla_fast_is_strictest(self):
        fast = SLA_TARGETS["slate-fast:latest"]
        coder = SLA_TARGETS["slate-coder:latest"]
        # Fast should have lower latency target (stricter)
        assert fast["max_latency_p95_ms"] < coder["max_latency_p95_ms"]
        # Fast should have higher throughput target (stricter)
        assert fast["min_throughput_tps"] > coder["min_throughput_tps"]

    def test_failover_chains_defined(self):
        assert "slate-coder:latest" in FAILOVER_CHAINS
        assert "slate-fast:latest" in FAILOVER_CHAINS
        assert "slate-planner:latest" in FAILOVER_CHAINS

    def test_failover_chains_not_empty(self):
        for model, chain in FAILOVER_CHAINS.items():
            assert len(chain) >= 1, f"{model} has empty failover chain"

    def test_ollama_url_is_localhost(self):
        assert "127.0.0.1" in OLLAMA_URL


# ── Data Classes ────────────────────────────────────────────────────────


class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    def test_create_healthy(self):
        result = HealthCheckResult(
            model="slate-fast:latest",
            timestamp="2026-07-12T00:00:00Z",
            status="healthy",
            latency_ms=500.0,
            tokens_per_sec=200.0,
            tokens_generated=10,
            gpu_index=0,
            gpu_memory_used_mb=4000,
            gpu_memory_total_mb=16000,
        )
        assert result.status == "healthy"
        assert result.error is None
        assert result.cold_start is False

    def test_create_unhealthy(self):
        result = HealthCheckResult(
            model="broken-model",
            timestamp="2026-07-12T00:00:00Z",
            status="unhealthy",
            latency_ms=0,
            tokens_per_sec=0,
            tokens_generated=0,
            gpu_index=0,
            gpu_memory_used_mb=0,
            gpu_memory_total_mb=0,
            error="Connection refused",
        )
        assert result.status == "unhealthy"
        assert result.error is not None

    def test_to_dict(self):
        result = HealthCheckResult(
            model="test",
            timestamp="now",
            status="healthy",
            latency_ms=100,
            tokens_per_sec=50,
            tokens_generated=5,
            gpu_index=0,
            gpu_memory_used_mb=0,
            gpu_memory_total_mb=0,
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["model"] == "test"


class TestSLAStatus:
    """Tests for SLAStatus dataclass."""

    def test_compliant_status(self):
        status = SLAStatus(
            model="slate-fast:latest",
            sla_target=SLA_TARGETS["slate-fast:latest"],
            latency_compliant=True,
            throughput_compliant=True,
            error_rate_compliant=True,
            availability_compliant=True,
            overall_compliant=True,
        )
        assert status.overall_compliant is True

    def test_non_compliant_status(self):
        status = SLAStatus(
            model="test",
            sla_target=SLA_TARGETS["_default"],
            latency_compliant=False,
            throughput_compliant=True,
            error_rate_compliant=True,
            availability_compliant=True,
            overall_compliant=False,
        )
        assert status.overall_compliant is False


class TestReadinessCheck:
    """Tests for ReadinessCheck dataclass."""

    def test_passing_check(self):
        check = ReadinessCheck(
            check_name="ollama_service",
            passed=True,
            message="Ollama running with 10 models",
        )
        assert check.passed is True
        assert check.severity == "info"

    def test_failing_check(self):
        check = ReadinessCheck(
            check_name="gpu_temperature",
            passed=False,
            message="GPU overheating: 95C",
            severity="critical",
        )
        assert check.passed is False
        assert check.severity == "critical"


class TestProductionReadiness:
    """Tests for ProductionReadiness dataclass."""

    def test_ready(self):
        pr = ProductionReadiness(
            timestamp="now",
            ready=True,
            score=0.9,
            checks=[],
            blocking_issues=[],
        )
        assert pr.ready is True
        assert pr.score == 0.9

    def test_not_ready_with_blocking(self):
        pr = ProductionReadiness(
            timestamp="now",
            ready=False,
            score=0.5,
            checks=[],
            blocking_issues=["No GPU available"],
        )
        assert pr.ready is False
        assert len(pr.blocking_issues) == 1


# ── GPU Info ────────────────────────────────────────────────────────────


class TestGPUInfo:
    """Tests for GPU info utilities."""

    @patch("subprocess.run")
    def test_get_gpu_info_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="0, NVIDIA GeForce RTX 5070 Ti, 4000, 16384, 30, 45\n"
                   "1, NVIDIA GeForce RTX 5070 Ti, 2000, 16384, 15, 40\n",
        )
        gpus = _get_gpu_info()
        assert len(gpus) == 2
        assert gpus[0]["index"] == 0
        assert gpus[0]["memory_total_mb"] == 16384
        assert gpus[1]["index"] == 1

    @patch("subprocess.run", side_effect=FileNotFoundError())
    def test_get_gpu_info_no_gpu(self, mock_run):
        gpus = _get_gpu_info()
        assert gpus == []


class TestOllamaModels:
    """Tests for Ollama model queries."""

    @patch("urllib.request.urlopen")
    def test_get_ollama_models(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "models": [
                {"name": "slate-fast:latest"},
                {"name": "slate-coder:latest"},
            ]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        models = _get_ollama_models()
        assert "slate-fast:latest" in models
        assert "slate-coder:latest" in models

    @patch("urllib.request.urlopen", side_effect=Exception("Connection refused"))
    def test_get_ollama_models_offline(self, mock_urlopen):
        models = _get_ollama_models()
        assert models == []


# ── SLA Checker ─────────────────────────────────────────────────────────


class TestSLAChecker:
    """Tests for SLA checker."""

    def test_sla_check_no_data(self, tmp_path, monkeypatch):
        monkeypatch.setattr("slate.slate_ai_production.HEALTH_LOG", tmp_path / "empty.jsonl")
        checker = SLAChecker()
        status = checker.check_sla("slate-fast:latest")
        assert status.overall_compliant is True  # No data = no violations
        assert status.metrics.get("note") == "No data yet"


# ── Health Monitor ──────────────────────────────────────────────────────


class TestHealthMonitor:
    """Tests for HealthMonitor."""

    def test_monitor_creation(self):
        monitor = HealthMonitor()
        assert isinstance(monitor.health_history, dict)


# ── Failover Manager ───────────────────────────────────────────────────


class TestFailoverManager:
    """Tests for FailoverManager."""

    @patch("slate.slate_ai_production._get_ollama_models",
           return_value=["slate-fast:latest", "mistral-nemo:latest", "llama3.2:3b", "mistral:latest"])
    def test_failover_for_coder(self, mock_models):
        fm = FailoverManager()
        fallback = fm.get_failover("slate-coder:latest")
        assert fallback == "mistral-nemo:latest"

    @patch("slate.slate_ai_production._get_ollama_models",
           return_value=["slate-fast:latest", "llama3.2:3b"])
    def test_failover_for_fast(self, mock_models):
        fm = FailoverManager()
        fallback = fm.get_failover("slate-fast:latest")
        assert fallback == "llama3.2:3b"

    @patch("slate.slate_ai_production._get_ollama_models",
           return_value=["some-model"])
    def test_failover_unknown_model(self, mock_models):
        fm = FailoverManager()
        fallback = fm.get_failover("unknown-model:latest")
        assert fallback == "some-model"  # Falls back to any available


# ── Production Manager ──────────────────────────────────────────────────


class TestProductionManager:
    """Tests for ProductionManager."""

    @patch("slate.slate_ai_production._get_ollama_models",
           return_value=["slate-fast:latest", "slate-coder:latest", "slate-planner:latest"])
    @patch("slate.slate_ai_production._get_running_models", return_value=[])
    def test_get_full_status(self, mock_running, mock_models):
        pm = ProductionManager()
        status = pm.get_full_status()
        assert "available_models" in status
        assert "slate_models" in status
        assert len(status["slate_models"]) == 3
        assert "gpus" in status
