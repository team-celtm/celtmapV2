from __future__ import annotations

import argparse
import sys

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Check CELTM hosted health and protected metrics endpoints.")
    parser.add_argument("--base-url", required=True, help="Backend base URL, for example https://api.example.com")
    parser.add_argument("--monitoring-token", default="", help="X-Monitoring-Token value for /system/metrics")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    failures: list[str] = []
    with httpx.Client(timeout=15) as client:
        health = client.get(f"{base_url}/health")
        if health.status_code != 200 or health.json().get("status") != "ok":
            failures.append(f"/health returned {health.status_code}: {health.text[:200]}")

        headers = {"X-Monitoring-Token": args.monitoring_token} if args.monitoring_token else {}
        metrics = client.get(f"{base_url}/system/metrics", headers=headers)
        if metrics.status_code != 200 or metrics.json().get("status") != "ok":
            failures.append(f"/system/metrics returned {metrics.status_code}: {metrics.text[:200]}")

    if failures:
        for failure in failures:
            print(f"FAILED: {failure}", file=sys.stderr)
        raise SystemExit(1)
    print("CELTM hosted health checks passed")


if __name__ == "__main__":
    main()
