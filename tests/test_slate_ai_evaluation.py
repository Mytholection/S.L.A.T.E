# Modified: 2026-07-12T02:50:00Z | Author: COPILOT | Change: Create tests for AI evaluation module
"""
Tests for slate/slate_ai_evaluation.py — golden tests, model evaluation,
benchmark runner, regression detection.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import asdict
from datetime import datetime, timezone

from slate.slate_ai_evaluation import (
    GOLDEN_TESTS,
    EVAL_DIR,
    BASELINES_FILE,
    TestResult,
    ModelScoreCard,
    RegressionAlert,
    ModelEvaluator,
    RegressionDetector,
    EvaluationSuite,
)


# ── Constants ───────────────────────────────────────────────────────────


class TestConstants:
    """Tests for evaluation constants."""

    def test_golden_tests_categories(self):
        expected = ["classification", "code_generation", "summarization", "code_review"]
        for cat in expected:
            assert cat in GOLDEN_TESTS, f"Missing golden test category: {cat}"

    def test_golden_tests_classification_count(self):
        assert len(GOLDEN_TESTS["classification"]) >= 4

    def test_golden_tests_code_generation_count(self):
        assert len(GOLDEN_TESTS["code_generation"]) >= 2

    def test_golden_tests_have_required_fields(self):
        for category, tests in GOLDEN_TESTS.items():
            for test in tests:
                assert "prompt" in test, f"{category} test missing 'prompt'"
                assert "expected_contains" in test, f"{category} test missing 'expected_contains'"

    def test_eval_dir_is_path(self):
        assert isinstance(EVAL_DIR, Path)

    def test_baselines_file_is_path(self):
        assert isinstance(BASELINES_FILE, Path)


# ── Data Classes ────────────────────────────────────────────────────────


class TestTestResult:
    """Tests for TestResult dataclass."""

    def test_create_test_result(self):
        result = TestResult(
            test_id="test-001",
            task_type="classification",
            model="slate-fast:latest",
            prompt_preview="Classify: fix the bug",
            expected_contains=["fix"],
            response_preview="fix",
            passed=True,
            score=0.95,
            latency_ms=500.0,
            tokens=10,
            tokens_per_sec=20.0,
        )
        assert result.passed is True
        assert result.score == 0.95
        assert result.model == "slate-fast:latest"

    def test_test_result_to_dict(self):
        result = TestResult(
            test_id="test-002",
            task_type="code_generation",
            model="slate-coder:latest",
            prompt_preview="Write fibonacci",
            expected_contains=["def", "fibonacci"],
            response_preview="def fibonacci(n):",
            passed=True,
            score=0.8,
            latency_ms=3000.0,
            tokens=100,
            tokens_per_sec=33.3,
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["test_id"] == "test-002"
        assert d["passed"] is True

    def test_test_result_failure(self):
        result = TestResult(
            test_id="fail-001",
            task_type="classification",
            model="bad-model",
            prompt_preview="classify this",
            expected_contains=["fix"],
            response_preview="",
            passed=False,
            score=0.0,
            latency_ms=100.0,
            tokens=0,
            tokens_per_sec=0,
            error="Connection refused",
        )
        assert result.passed is False
        assert result.error is not None


class TestModelScoreCard:
    """Tests for ModelScoreCard dataclass."""

    def test_empty_scorecard(self):
        card = ModelScoreCard(
            model="test-model",
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            total_tests=0,
            passed_tests=0,
            avg_score=0.0,
            avg_latency_ms=0.0,
            avg_tokens_per_sec=0.0,
            scores_by_task={},
            test_results=[],
        )
        assert card.pass_rate == 0.0

    def test_scorecard_pass_rate(self):
        card = ModelScoreCard(
            model="slate-fast:latest",
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            total_tests=10,
            passed_tests=8,
            avg_score=0.8,
            avg_latency_ms=500.0,
            avg_tokens_per_sec=50.0,
            scores_by_task={"classification": 0.9, "code_generation": 0.7},
            test_results=[],
        )
        assert card.pass_rate == 0.8

    def test_scorecard_to_dict(self):
        card = ModelScoreCard(
            model="test-model",
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            total_tests=5,
            passed_tests=4,
            avg_score=0.85,
            avg_latency_ms=300.0,
            avg_tokens_per_sec=60.0,
            scores_by_task={},
            test_results=[],
        )
        d = card.to_dict()
        assert isinstance(d, dict)
        assert d["model"] == "test-model"
        assert "pass_rate" in d


class TestRegressionAlert:
    """Tests for RegressionAlert dataclass."""

    def test_create_alert(self):
        alert = RegressionAlert(
            model="slate-fast:latest",
            metric="pass_rate",
            baseline_value=0.95,
            current_value=0.80,
            threshold_pct=-15.8,
            severity="warning",
            message="pass_rate regressed by 15.8%",
        )
        assert alert.severity == "warning"
        assert alert.threshold_pct < 0

    def test_alert_to_dict(self):
        alert = RegressionAlert(
            model="test",
            metric="latency",
            baseline_value=100.0,
            current_value=130.0,
            threshold_pct=30.0,
            severity="critical",
            message="latency regressed by 30%",
        )
        d = alert.to_dict()
        assert isinstance(d, dict)
        assert d["severity"] == "critical"


# ── ModelEvaluator ──────────────────────────────────────────────────────


class TestModelEvaluator:
    """Tests for ModelEvaluator class."""

    def test_evaluator_creation(self):
        evaluator = ModelEvaluator("slate-fast:latest")
        assert evaluator.model == "slate-fast:latest"


# ── RegressionDetector ──────────────────────────────────────────────────


class TestRegressionDetector:
    """Tests for RegressionDetector class."""

    def test_detector_creation(self, tmp_path):
        detector = RegressionDetector()
        assert detector is not None
        assert detector.WARNING_THRESHOLD > 0
        assert detector.CRITICAL_THRESHOLD > detector.WARNING_THRESHOLD

    def test_no_regression_without_baselines(self, tmp_path, monkeypatch):
        monkeypatch.setattr("slate.slate_ai_evaluation.BASELINES_FILE", tmp_path / "none.json")
        detector = RegressionDetector()
        current = ModelScoreCard(
            model="test",
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            total_tests=5,
            passed_tests=5,
            avg_score=1.0,
            avg_latency_ms=100.0,
            avg_tokens_per_sec=50.0,
            scores_by_task={},
            test_results=[],
        )
        alerts = detector.check_regressions(current)
        assert isinstance(alerts, list)
        assert len(alerts) == 0


# ── EvaluationSuite ─────────────────────────────────────────────────────


class TestEvaluationSuite:
    """Tests for EvaluationSuite class."""

    def test_suite_creation(self):
        suite = EvaluationSuite()
        assert suite is not None

    def test_get_status(self):
        suite = EvaluationSuite()
        status = suite.get_status()
        assert isinstance(status, dict)
        assert "golden_test_count" in status
        assert status["golden_test_count"] > 0
