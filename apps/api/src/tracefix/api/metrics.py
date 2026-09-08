from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

WEBHOOKS = Counter("tracefix_webhooks_total", "Webhook deliveries", ["result"])
RUNS = Counter("tracefix_runs_total", "Repair runs", ["state"])
VERIFY = Counter("tracefix_verification_total", "Verification outcomes", ["result"])
HTTP_LATENCY = Histogram("tracefix_http_duration_seconds", "HTTP duration", ["path"])


def scrape() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
