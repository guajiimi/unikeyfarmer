#!/usr/bin/env python3
"""UNIKEY API client — register, create key, precheck. Thread-safe per session."""
import datetime

from curl_cffi import requests
from eth_account import Account
from eth_account.messages import encode_defunct

import config
from logsetup import worker_logger
from solver import solve_turnstile

CHAIN_ID = 56  # BSC, hardcoded client-side
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class UnikeyClient:
    def __init__(self, proxy: str | None, log):
        self.proxy = proxy
        self.log = log
        self.s = requests.Session(
            impersonate="chrome124",
            proxies={"http": proxy, "https": proxy} if proxy else None,
        )
        self.s.headers.update({"User-Agent": UA})
        self.uid: int | None = None

    # ── low-level ────────────────────────────────────────────
    def _post(self, url: str, retries: int = 4, **kw):
        """POST with 429/5xx retry. ESA 429/524 = empty body."""
        last = None
        for attempt in range(1, retries + 1):
            r = self.s.post(url, timeout=30, **kw)
            if r.status_code == 200 and r.content:
                return r
            last = r
            wait = 20 * attempt if r.status_code == 429 else 10
            self.log.warning(
                f"HTTP {r.status_code} {url.split('/api/')[-1].split('?')[0]} "
                f"→ retry {attempt}/{retries} in {wait}s"
            )
            import time

            time.sleep(wait)
        return last

    def _api(self, method: str, path: str, retries: int = 4, **kw):
        url = f"{config.BASE_URL}{path}"
        if self.uid:
            kw.setdefault("headers", {})
            kw["headers"]["New-Api-User"] = str(self.uid)
        last = None
        for attempt in range(1, retries + 1):
            r = self.s.request(method, url, timeout=30, **kw)
            if r.status_code == 200 and r.content:
                return r
            last = r
            wait = 20 * attempt if r.status_code == 429 else 10
            self.log.warning(
                f"HTTP {r.status_code} {path} → retry {attempt}/{retries} in {wait}s"
            )
            import time

            time.sleep(wait)
        return last

    # ── pipeline steps ───────────────────────────────────────
    def warmup(self):
        self.s.get(f"{config.BASE_URL}/", timeout=20)
        n = len(self.s.cookies.get_dict())
        if n == 0:
            raise RuntimeError("ESA warm-up failed, 0 cookies")
        self.log.debug(f"warm-up ok ({n} cookies)")

    def register(self) -> dict:
        """Fresh wallet → register → logged-in user data."""
        pk = Account.create().key.hex()[2:]
        self.acct = Account.from_key(pk.zfill(64))
        self.private_key = "0x" + pk.zfill(64)
        addr = self.acct.address
        self.log.info(f"wallet {addr}")

        # challenge
        r = self._post(
            f"{config.BASE_URL}/api/oauth/web3/challenge",
            json={"wallet_address": addr},
            headers={"Origin": config.BASE_URL, "Referer": f"{config.BASE_URL}/login"},
        )
        j = r.json()
        if not j.get("success"):
            raise RuntimeError(f"challenge: {r.text[:150]}")
        message = j["data"]["message"]
        nonce = j["data"]["nonce"]
        self.log.debug(f"challenge ok nonce={nonce[:12]}…")

        # sign
        sig = "0x" + self.acct.sign_message(
            encode_defunct(text=message)
        ).signature.hex()

        # turnstile
        token = solve_turnstile(f"{config.BASE_URL}/login")
        self.log.debug("turnstile solved")

        # verify
        r = self._post(
            f"{config.BASE_URL}/api/oauth/web3/verify",
            params={"turnstile": token, "hcaptcha": ""},
            json={
                "action": "login",
                "wallet_address": addr,
                "nonce": nonce,
                "signature": sig,
                "chain_id": CHAIN_ID,
            },
            headers={"Origin": config.BASE_URL, "Referer": f"{config.BASE_URL}/login"},
        )
        j = r.json()
        if not j.get("success"):
            raise RuntimeError(f"verify: HTTP {r.status_code} {r.text[:150]}")
        self.uid = j["data"]["id"]
        self.log.info(
            f"registered → uid={self.uid} user={j['data']['username']} ({j['data']['group']})"
        )
        return j["data"]

    def create_api_key(self) -> str:
        H = {"Origin": config.BASE_URL, "Referer": f"{config.BASE_URL}/console"}
        r = self._api(
            "POST",
            "/api/token/",
            json={
                "name": "api",
                "remain_quota": 0,
                "expired_time": -1,
                "unlimited_quota": True,
                "model_limits_enabled": False,
                "model_limits": "",
                "allow_ips": "",
                "group": "",
                "cross_group_retry": True,
            },
            headers=H,
        )
        if not r.json().get("success"):
            raise RuntimeError(f"token create: {r.text[:150]}")
        lst = self._api("GET", "/api/token/?p=1&size=10", headers=H).json()
        tid = lst["data"]["items"][0]["id"]

        rk = self._api("POST", f"/api/token/{tid}/key", headers=H).json()
        if not rk.get("success"):
            raise RuntimeError(f"key reveal: {rk}")
        key = "sk-" + rk["data"]["key"]
        self.log.info(f"api key {key[:10]}…{key[-6:]} (token {tid})")
        return key

    def quota(self) -> dict:
        r = self._api("GET", "/api/user/self")
        return (r.json().get("data") or {})

    def precheck(self, key: str) -> bool:
        """Validate api_key via minimal chat completion on /v1."""
        for attempt in range(1, 4):
            try:
                r = self.s.post(
                    f"{config.API_BASE_URL}/chat/completions",
                    json={
                        "model": config.PRECHECK_MODEL,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 10,
                    },
                    headers={"Authorization": f"Bearer {key}"},
                    timeout=90,
                )
                if r.status_code == 200 and r.content:
                    j = r.json()
                    if j.get("choices"):
                        content = j["choices"][0]["message"]["content"]
                        self.log.success(
                            f"precheck OK → {j['model']} replied {content[:20]!r}"
                        )
                        return True
                self.log.warning(
                    f"precheck HTTP {r.status_code} len={len(r.content)} ({attempt}/3)"
                )
            except Exception as e:
                self.log.warning(f"precheck err {str(e)[:60]} ({attempt}/3)")
            import time

            time.sleep(8)
        return False

    # ── full pipeline ────────────────────────────────────────
    def run(self) -> dict | None:
        self.warmup()
        user = self.register()
        key = self.create_api_key()
        q = self.quota()

        acc = {
            "address": self.acct.address,
            "private_key": self.private_key,
            "uid": self.uid,
            "username": user.get("username"),
            "api_key": key,
            "quota": q.get("quota"),
            "used_quota": q.get("used_quota"),
            "valid": False,
            "proxy": self.proxy,
            "registered_at": datetime.datetime.now().isoformat(),
        }
        acc["valid"] = self.precheck(key)
        acc["status"] = "VALID" if acc["valid"] else "KEY_UNCHECKED"
        return acc
