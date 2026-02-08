# Modified: 2026-07-12T02:50:00Z | Author: COPILOT | Change: Create tests for AI tracing module
"""
Tests for slate/slate_ai_tracing.py — inference tracing, metrics, export.
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from slate.slate_ai_tracing import (
    InferenceTrace,
    ModelMetrics,
    JSONFileExporter,
    SlateAITracer,
    get_gpu_snapshot,
    get_tracer,
    TRACE_DIR,
    METRICS_FILE,
    _otel_available,
)


# ── Data Classes ────────────────────────────────────────────────────────


class TestInferenceTrace:
    """Tests for InferenceTrace dataclass."""

    def test_create_trace(self):
        trace = InferenceTrace(
            trace_id="test-001",
            span_id="span-001",
            timestamp="2026-07-12T00:00:00Z",
            model="slate-fast:latest",
            task_type="classification",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            latency_ms=100.0,
            eval_time_ms=80.0,
            tokens_per_sec=62.5,
            gpu_index=0,
            gpu_memory_used_mb=2000,
            gpu_memory_total_mb=16000,
            status="success",
        )
        assert trace.trace_id == "test-001"
        assert trace.total_tokens == 15
        assert trace.status == "success"
        assert trace.error is None

    def test_trace_to_dict(self):
        trace = InferenceTrace(
            trace_id="test-002",
            span_id="span-002",
            timestamp="2026-07-12T00:00:00Z",
            model="slate-coder:latest",
            task_type="code_generation",
            prompt_tokens=50,
            completion_tokens=100,
            total_tokens=150,
            latency_ms=5000.0,
            eval_time_ms=4500.0,
            tokens_per_sec=22.2,
            gpu_index=0,
            gpu_memory_used_mb=8000,
            gpu_memory_total_mb=16000,
            status="success",
        )
        d = trace.to_dict()
        assert isinstance(d, dict)
        assert d["model"] == "slate-coder:latest"
        assert d["total_tokens"] == 150
        assert "trace_id" in d
        assert "error" in d

    def test_trace_with_error(self):
        trace = InferenceTrace(
            trace_id="err-001",
            span_id="span-err",
            timestamp="2026-07-12T00:00:00Z",
            model="slate-fast:latest",
            task_type="classification",
            prompt_tokens=10,
            completion_tokens=0,
            total_tokens=10,
            latency_ms=100.0,
            eval_time_ms=0,
            tokens_per_sec=0,
            gpu_index=0,
            gpu_memory_used_mb=0,
            gpu_memory_total_mb=0,
            status="error",
            error="Connection timeout",
        )
        assert trace.status == "error"
        assert trace.error == "Connection timeout"


class TestModelMetrics:
    """Tests for ModelMetrics dataclass."""

    def test_empty_metrics(self):
        mm = ModelMetrics(model="test-model")
        assert mm.total_calls == 0
        assert mm.avg_latency_ms == 0.0
        assert mm.avg_tokens_per_sec == 0.0
        assert mm.p50_latency_ms == 0.0
        assert mm.p95_latency_ms == 0.0
        assert mm.p99_latency_ms == 0.0
        assert mm.error_rate == 0.0

    def test_metrics_aggregation(self):
        mm = ModelMetrics(model="test-model")
        mm.total_calls = 10
        mm.total_tokens = 500
        mm.total_latency_ms = 5000.0
        mm.error_count = 1
        mm.latencies_ms = [400, 450, 500, 550, 600, 450, 500, 520, 480, 510]
        mm.tokens_per_sec_values = [50.0, 55.0, 60.0, 45.0, 52.0]
        assert mm.avg_latency_ms == 500.0
        assert mm.error_rate == 0.1
        assert mm.p50_latency_ms > 0
        assert mm.p95_latency_ms >= mm.p50_latency_ms

    def test_metrics_to_dict(self):
        mm = ModelMetrics(model="test-model")
        mm.total_calls = 5
        mm.total_tokens = 200
        mm.latencies_ms = [100, 200, 300]
        mm.tokens_per_sec_values = [50.0, 60.0]
        d = mm.to_dict()
        assert isinstance(d, dict)
        assert d["model"] == "test-model"
        assert d["total_calls"] == 5
        assert "avg_latency_ms" in d
        assert "p95_latency_ms" in d
        assert "avg_tokens_per_sec" in d


# ── JSON File Exporter ──────────────────────────────────────────────────


class TestJSONFileExporter:
    """Tests for JSONFileExporter."""

    def test_export_and_read(self, tmp_path):
        filepath = tmp_path / "traces" / "test.jsonl"
        exporter = JSONFileExporter(filepath)

        trace = InferenceTrace(
            trace_id="exp-001",
            span_id="span-001",
            timestamp="2026-07-12T00:00:00Z",
            model="slate-fast:latest",
            task_type="classification",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            latency_ms=100.0,
            eval_time_ms=80.0,
            tokens_per_sec=62.5,
            gpu_index=0,
            gpu_memory_used_mb=2000,
            gpu_memory_total_mb=16000,
            status="success",
        )
        exporter.export_trace(trace)

        records = exporter.read_all()
        assert len(records) == 1
        assert records[0]["trace_id"] == "exp-001"

    def test_multiple_exports(self, tmp_path):
        filepath = tmp_path / "traces.jsonl"
        exporter = JSONFileExporter(filepath)

        for i in range(5):
            trace = InferenceTrace(
                trace_id=f"multi-{i:03d}",
                span_id=f"span-{i:03d}",
                timestamp="2026-07-12T00:00:00Z",
                model="test-model",
                task_type="test",
                prompt_tokens=i,
                completion_tokens=i * 2,
                total_tokens=i * 3,
                latency_ms=100.0 + i,
                eval_time_ms=80.0,
                tokens_per_sec=50.0,
                gpu_index=0,
                gpu_memory_used_mb=0,
                gpu_memory_total_mb=0,
                status="success",
            )
            exporter.export_trace(trace)

        records = exporter.read_all()
        assert len(records) == 5

    def test_read_empty_file(self, tmp_path):
        filepath = tmp_path / "empty.jsonl"
        exporter = JSONFileExporter(filepath)
        records = exporter.read_all()
        assert records == []


# ── GPU Snapshot ────────────────────────────────────────────────────────


class TestGPUSnapshot:
    """Tests for GPU snapshot utility."""

    @patch("subprocess.run")
    def test_gpu_snapshot_success(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="0, 4000, 16384, 30\n"
                   "1, 2000, 16384, 15\n",
        )
        result = get_gpu_snapshot(0)
        assert result["gpu_index"] == 0
        assert result["memory_used_mb"] == 4000
        assert result["memory_total_mb"] == 16384

    @patch("subprocess.run", side_effect=FileNotFoundError("nvidia-smi not found"))
    def test_gpu_snapshot_no_gpu(self, mock_run):
        result = get_gpu_snapshot(0)
        assert result["gpu_index"] == 0
        assert result["memory_used_mb"] == 0


# ── SlateAITracer ───────────────────────────────────────────────────────


class TestSlateAITracer:
    """Tests for SlateAITracer class."""

    def test_tracer_creation(self):
        tracer = SlateAITracer(enable_otel=False)
        assert tracer is not None
        assert isinstance(tracer.model_metrics, dict)

    def test_trace_inference(self, tmp_path, monkeypatch):
        monkeypatch.setattr("slate.slate_ai_tracing.TRACE_DIR", tmp_path / "traces")
        monkeypatch.setattr("slate.slate_ai_tracing.METRICS_FILE", tmp_path / "traces" / "metrics.json")

        tracer = SlateAITracer(enable_otel=False)
        tracer.json_exporter = JSONFileExporter(tmp_path / "traces" / "test.jsonl")

        result = {
            "response": "OK",
            "eval_count": 5,
            "prompt_eval_count": 10,
            "eval_duration": 500_000_000,  # 500ms in ns
        }

        with patch("slate.slate_ai_tracing.get_gpu_snapshot", return_value={
            "gpu_index": 0, "memory_used_mb": 4000, "memory_total_mb": 16384, "utilization_pct": 30,
        }):
            trace = tracer.trace_inference(
                model="slate-fast:latest",
                task_type="classification",
                prompt="Test prompt",
                result=result,
                elapsed=0.5,
                gpu_index=0,
            )

        assert trace.model == "slate-fast:latest"
        assert trace.status == "success"
        assert trace.completion_tokens == 5
        assert trace.prompt_tokens == 10
        assert trace.tokens_per_sec == 10.0  # 5 tokens / 0.5s
        assert "slate-fast:latest" in tracer.model_metrics

    def test_get_metrics(self):
        tracer = SlateAITracer(enable_otel=False)
        tracer.model_metrics["test-model"] = ModelMetrics(model="test-model")
        tracer.model_metrics["test-model"].total_calls = 10
        tracer.model_metrics["test-model"].total_tokens = 500

        metrics = tracer.get_metrics()
        assert metrics["summary"]["total_calls"] == 10
        assert metrics["summary"]["total_tokens"] == 500
        assert "test-model" in metrics["models"]

    def test_generate_report(self):
        tracer = SlateAITracer(enable_otel=False)
        tracer.model_metrics["test-model"] = ModelMetrics(model="test-model")
        tracer.model_metrics["test-model"].total_calls = 5

        report = tracer.generate_report()
        assert "SLATE AI Tracing Report" in report
        assert "test-model" in report


# ── Singleton ───────────────────────────────────────────────────────────


class TestGetTracer:
    """Tests for tracer singleton."""

    def test_get_tracer_returns_instance(self):
        tracer = get_tracer()
        assert isinstance(tracer, SlateAITracer)
