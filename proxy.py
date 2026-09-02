#!/usr/bin/env python3
"""Proxy loader — proxy.txt, one per line.

Supported:
  http://user:pass@host:port
  socks5://host:port
  direct            -> no proxy (VPS IP)
Lines starting with # skipped.
"""
import random
from pathlib import Path

from curl_cffi import requests


def load_proxies(path: Path) -> list[str | None]:
    proxies: list[str | None] = []
    if not path.exists():
        return proxies
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower() == "direct":
            proxies.append(None)
        elif "://" in line:
            proxies.append(line)
        else:
            proxies.append(f"http://{line}")
    return proxies


def check_proxy(proxy: str | None, timeout: int = 15) -> tuple[bool, str]:
    """Quick IP check — returns (ok, ip_or_error)."""
    try:
        kwargs = {}
        if proxy:
            kwargs["proxies"] = {"http": proxy, "https": proxy}
        r = requests.get(
            "https://api.ipify.org", timeout=timeout, impersonate="chrome124", **kwargs
        )
        return True, r.text.strip()
    except Exception as e:
        return False, str(e)[:80]


def tag(proxy: str | None) -> str:
    """Short display tag for a proxy."""
    if proxy is None:
        return "direct"
    # strip scheme + creds
    tail = proxy.split("://", 1)[-1]
    if "@" in tail:
        tail = tail.split("@", 1)[-1]
    host = tail.split(":")[0]
    port = tail.split(":")[1].split("/")[0] if ":" in tail else "?"
    return f"{host}:{port}"


def pick(proxies: list[str | None], exclude: set[int]) -> str | None:
    """Random pick excluding already-used indexes."""
    avail = [i for i in range(len(proxies)) if i not in exclude]
    if not avail:
        return None
    return proxies[random.choice(avail)]
