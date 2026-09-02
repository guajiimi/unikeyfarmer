#!/usr/bin/env python3
"""Capsolver Turnstile solver (proxyless — UNIKEY token is NOT IP-bound)."""
import time

from curl_cffi import requests

import config


def solve_turnstile(website_url: str, timeout: int = 180) -> str:
    s = requests.Session(impersonate="chrome124")
    r = s.post(
        "https://api.capsolver.com/createTask",
        json={
            "clientKey": config.CAPSOLVER_KEY,
            "task": {
                "type": "AntiTurnstileTaskProxyLess",
                "websiteURL": website_url,
                "websiteKey": config.TURNSTILE_SITEKEY,
            },
        },
        timeout=30,
    ).json()
    if r.get("errorId"):
        raise RuntimeError(f"capsolver createTask: {r.get('errorCode')}")
    task_id = r["taskId"]

    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(3)
        r = s.post(
            "https://api.capsolver.com/getTaskResult",
            json={"clientKey": config.CAPSOLVER_KEY, "taskId": task_id},
            timeout=30,
        ).json()
        if r.get("status") == "ready":
            return r["solution"]["token"]
        if r.get("errorId"):
            raise RuntimeError(f"capsolver result: {r.get('errorCode')}")
    raise RuntimeError("capsolver timeout")
