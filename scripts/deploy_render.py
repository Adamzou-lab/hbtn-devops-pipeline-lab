#!/usr/bin/env python3
"""Deploy one tested image and require live deployment plus database readiness."""

import json
import os
import sys
import time
import urllib.error
import urllib.request


def api(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        "https://api.render.com/v1" + path,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + os.environ["RENDER_API_KEY"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main():
    service = os.environ["RENDER_SERVICE_ID"]
    image = os.environ["DEPLOY_IMAGE"]
    staging = os.environ["STAGING_URL"].rstrip("/")
    if not service.startswith("srv-") or not staging.startswith("https://"):
        raise ValueError("Configure RENDER_SERVICE_ID and the HTTPS STAGING_URL")
    deploy = api("POST", f"/services/{service}/deploys", {
        "imageUrl": image,
        "clearCache": "do_not_clear",
    })
    deploy_id = deploy["id"]
    print(f"Deploying {image}; Render deployment {deploy_id}", flush=True)
    for attempt in range(45):
        status = api("GET", f"/services/{service}/deploys/{deploy_id}")["status"]
        print(f"Deployment check {attempt + 1}/45: {status}", flush=True)
        if status == "live":
            break
        if status in {"build_failed", "update_failed", "pre_deploy_failed", "canceled", "deactivated"}:
            raise RuntimeError(f"Render deployment ended with {status}")
        time.sleep(10)
    else:
        raise RuntimeError("Render deployment did not become live before the deadline")

    # /health alone is insufficient: /items proves PostgreSQL is reachable.
    for attempt in range(20):
        checks = {}
        for path in ("/health", "/items"):
            try:
                with urllib.request.urlopen(staging + path, timeout=10) as response:
                    checks[path] = response.status
            except urllib.error.HTTPError as error:
                checks[path] = error.code
            except (urllib.error.URLError, TimeoutError):
                checks[path] = "unreachable"
        print(f"Readiness check {attempt + 1}/20: {checks}", flush=True)
        if all(status == 200 for status in checks.values()):
            print("Staging is live and database readiness passed.")
            return
        time.sleep(10)
    raise RuntimeError("Staging did not return HTTP 200 from both endpoints")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Never print API response bodies or credential-bearing headers.
        print(f"Deployment failed: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
