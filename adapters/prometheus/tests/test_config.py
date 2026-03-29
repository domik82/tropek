"""Tests for adapter configuration defaults and env-var overrides."""

import os

import pytest

from app.config import Settings


def test_default_settings():
    s = Settings()
    assert s.port == 8080
    assert s.prometheus_url == "http://localhost:9090"
    assert s.redis_url == "redis://localhost:6379/0"
    assert s.redis_key_prefix == "prom-sli:"
    assert s.max_concurrent_queries == 10
    assert s.max_concurrent_jobs == 3
    assert s.max_queue_depth == 100
    assert s.max_queries_per_job == 400
    assert s.default_job_timeout_seconds == 120
    assert s.max_job_timeout_seconds == 600
    assert s.query_timeout_seconds == 30
    assert s.job_retention_seconds == 3600
    assert s.default_chunk_size == "4h"
    assert s.default_parallel_chunks == 3
    assert s.log_level == "INFO"


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAX_CONCURRENT_QUERIES", "20")
    monkeypatch.setenv("PROMETHEUS_URL", "http://prom:9090")
    s = Settings()
    assert s.max_concurrent_queries == 20
    assert s.prometheus_url == "http://prom:9090"
