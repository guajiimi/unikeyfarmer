#!/usr/bin/env python3
"""Loguru custom console logging — UNIKEY Farmer style."""
import sys

from loguru import logger

_FMT = (
    "<green>{time:HH:mm:ss}</green> "
    "<level>{level: <7}</level> "
    "<light-white>{extra[prefix]}</light-white> "
    "<level>{message}</level>"
)


def setup(verbose: bool = False):
    logger.remove()
    logger.configure(extra={"prefix": "-"})  # default utk record tanpa bind
    logger.add(
        sys.stderr,
        format=_FMT,
        level="DEBUG" if verbose else "INFO",
        colorize=True,
        backtrace=False,
        diagnose=False,
    )
    return logger


def worker_logger(worker_id: int, proxy_tag: str):
    """Per-worker logger with [W1|proxy] prefix."""
    return logger.bind(prefix=f"[W{worker_id}|{proxy_tag}]")


def main_logger():
    return logger.bind(prefix="[MAIN]")
