#!/usr/bin/env python3
"""
UNIKEY Farmer — register → create api key → precheck
getunikey.ai (new-api fork) • pure HTTP • multi-thread

Interactive CLI, config dari .env, proxy dari proxy.txt.
"""
import json
import queue as queue_mod
import threading
import time
from queue import Queue

from logsetup import main_logger, setup, worker_logger
from proxy import check_proxy, load_proxies, tag
from client import UnikeyClient
import config

log = None  # set in main()


def ask_int(prompt: str, default: int, lo: int, hi: int) -> int:
    while True:
        raw = input(f"  {prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            v = int(raw)
            if lo <= v <= hi:
                return v
            print(f"  → masukkan angka {lo}–{hi}")
        except ValueError:
            print("  → angka valid saja")


def ask_proxies(n_workers: int, proxies: list) -> list:
    """Assign proxy per worker (unique). Return list index ke proxies."""
    print(f"\n  Proxy tersedia: {len(proxies)}")
    mode = input("  Mode proxy: [r]andom unique / [s]equential / enter=auto → ").strip().lower()

    n = len(proxies)
    if n == 0:
        print("  ⚠ proxy.txt kosong → semua worker pakai direct IP")
        return [None] * n_workers
    if n < n_workers:
        print(f"  ⚠ proxy ({n}) < worker ({n_workers}) → worker reuse proxy (cycle)")

    if mode == "s":
        return [proxies[i % n] if n else None for i in range(n_workers)]
    # random unique (cycle kalau kurang)
    import random

    pool = proxies * (n_workers // n + 1)
    random.shuffle(pool)
    return pool[:n_workers]


def save_accounts(accs: list):
    old = []
    if config.ACCOUNTS_FILE.exists():
        try:
            old = json.load(open(config.ACCOUNTS_FILE))
            if not isinstance(old, list):
                old = []
        except Exception:
            old = []
    config.ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    json.dump(old + accs, open(config.ACCOUNTS_FILE, "w"), indent=2)


def worker(wid: int, proxy: str | None, q: Queue, results: list, lock: threading.Lock, stats: dict):
    lg = worker_logger(wid, tag(proxy))
    while True:
        try:
            idx = q.get_nowait()
        except queue_mod.Empty:
            return
        try:
            t0 = time.time()
            acc = UnikeyClient(proxy, lg).run()
            dt = time.time() - t0
            with lock:
                results.append(acc)
                if acc["valid"]:
                    stats["valid"] += 1
                else:
                    stats["unchecked"] += 1
            lg.success(
                f"#{idx} done in {dt:.1f}s → {acc['status']} "
                f"quota={acc.get('quota')} addr={acc['address'][:10]}…"
            )
        except Exception as e:
            with lock:
                stats["fail"] += 1
            lg.error(f"#{idx} failed: {str(e)[:120]}")
        finally:
            q.task_done()


def banner():
    print(
        """
╔══════════════════════════════════════════════╗
║   UNIKEY FARMER  •  getunikey.ai             ║
║   register → api key → precheck              ║
╚══════════════════════════════════════════════╝"""
    )


def main():
    global log
    log = setup()
    banner()

    if not config.CAPSOLVER_KEY:
        log.error("CAPSOLVER_KEY kosong di .env")
        return

    proxies = load_proxies(config.PROXY_FILE)
    print()
    log.info(f"config: base={config.BASE_URL} model={config.PRECHECK_MODEL}")
    log.info(f"proxy file: {config.PROXY_FILE.name} → {len(proxies)} proxy")
    print()

    n_accounts = ask_int("Mau berapa akun?", 5, 1, 500)
    max_w = min(n_accounts, 20)
    if len(proxies) < n_accounts:
        max_w = min(max_w, max(1, len(proxies))) if proxies else 4
    n_workers = ask_int("Berapa thread worker?", min(3, max_w), 1, max_w)

    assigned = ask_proxies(n_workers, proxies)

    print()
    log.info("cek proxy per worker…")
    worker_proxies = []
    for i, p in enumerate(assigned, 1):
        ok, info = check_proxy(p)
        wtag = tag(p)
        status = "ok" if ok else "DEAD"
        ip = info if ok else info
        log.info(f"  W{i} {wtag} → {status} ip={ip}")
        if ok or p is None:
            worker_proxies.append(p)
        else:
            log.warning(f"  W{i} {wtag} proxy mati → pakai direct")
            worker_proxies.append(None)

    print()
    log.info(f"start: {n_accounts} akun / {len(worker_proxies)} worker")
    print()

    q = Queue()
    for i in range(1, n_accounts + 1):
        q.put(i)

    results: list = []
    lock = threading.Lock()
    stats = {"valid": 0, "unchecked": 0, "fail": 0}
    threads = []
    for wid, p in enumerate(worker_proxies, 1):
        t = threading.Thread(
            target=worker, args=(wid, p, q, results, lock, stats), daemon=True
        )
        t.start()
        threads.append(t)
        time.sleep(1.5)  # stagger start

    for t in threads:
        t.join()

    save_accounts(results)
    print()
    log.success(
        f"SELESAI → valid: {stats['valid']} | unchecked: {stats['unchecked']} | "
        f"fail: {stats['fail']} | saved: {config.ACCOUNTS_FILE.name} ({len(results)} new)"
    )


if __name__ == "__main__":
    main()
