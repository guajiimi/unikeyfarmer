#!/usr/bin/env python3
"""Config loader — reads .env, no hardcoded keys."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")


def get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


CAPSOLVER_KEY = get("CAPSOLVER_KEY")
TURNSTILE_SITEKEY = get("TURNSTILE_SITEKEY", "0x4AAAAAAD83S5lYamgIOFL4")
BASE_URL = get("BASE_URL", "https://www.getunikey.ai")
API_BASE_URL = get("API_BASE_URL", BASE_URL + "/v1")
PRECHECK_MODEL = get("PRECHECK_MODEL", "google/gemini-3.1-flash-lite")
PROXY_FILE = ROOT / get("PROXY_FILE", "proxy.txt")
ACCOUNTS_FILE = ROOT / get("ACCOUNTS_FILE", "output/accounts.json")
