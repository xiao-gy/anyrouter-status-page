#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
from pathlib import Path

from flask import Flask, send_from_directory

PROJECT_ROOT = Path(__file__).resolve().parent
DOCS_DIR = PROJECT_ROOT / "docs"
ENV_PATH = PROJECT_ROOT / ".env"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))
from check_anyrouter import (  # noqa: E402
    HISTORY_PATH,
    STATUS_PATH,
    default_history,
    load_json,
    merge_history,
    run_probe,
    write_json,
)

log = logging.getLogger("anyrouter.scheduler")
_scheduler_lock = threading.Lock()
_scheduler_started = False


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env_truthy(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def run_check_once() -> None:
    api_base = os.environ.get("ANYROUTER_API_BASE", "").strip()
    api_key = os.environ.get("ANYROUTER_API_KEY", "").strip()
    if not api_base or not api_key:
        log.warning("Skip scheduled probe: ANYROUTER_API_BASE/ANYROUTER_API_KEY not set")
        return

    model = os.environ.get("ANYROUTER_MODEL", "claude-opus-4-7[1m]")
    timeout = int(os.environ.get("ANYROUTER_TIMEOUT", "30"))
    prompt = os.environ.get("ANYROUTER_PROMPT", "Reply with exactly one visible character: A")
    proxy = (
        os.environ.get("ANYROUTER_PROXY")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("HTTP_PROXY")
        or None
    )

    snapshot = run_probe(api_base, api_key, model, timeout, prompt, proxy)
    history = load_json(HISTORY_PATH, default_history())
    merged = merge_history(history, snapshot)
    write_json(STATUS_PATH, snapshot)
    write_json(HISTORY_PATH, merged)
    log.info(
        "Probe done: status=%s http=%s latency=%sms",
        snapshot.get("overall_status"),
        snapshot.get("http_status"),
        snapshot.get("latency_ms"),
    )


def _scheduler_loop(interval: int, run_on_start: bool) -> None:
    if run_on_start:
        try:
            run_check_once()
        except Exception:
            log.exception("Probe failed at startup")
    while True:
        time.sleep(interval)
        try:
            run_check_once()
        except Exception:
            log.exception("Probe failed")


def start_scheduler() -> None:
    global _scheduler_started
    interval = int(os.environ.get("CHECK_INTERVAL_SECONDS", "0"))
    if interval <= 0:
        return
    # avoid double-start under Flask debug reloader (parent + child process)
    if os.environ.get("FLASK_DEBUG") == "1" and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True
    run_on_start = _env_truthy("CHECK_ON_STARTUP", True)
    log.info("Scheduler started: interval=%ss run_on_start=%s", interval, run_on_start)
    t = threading.Thread(
        target=_scheduler_loop,
        args=(interval, run_on_start),
        daemon=True,
        name="anyrouter-scheduler",
    )
    t.start()


def create_app() -> Flask:
    load_dotenv(ENV_PATH)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = Flask(__name__, static_folder=None)

    @app.route("/")
    def index():
        return send_from_directory(DOCS_DIR, "index.html")

    @app.route("/<path:filename>")
    def static_files(filename: str):
        return send_from_directory(DOCS_DIR, filename)

    @app.route("/healthz")
    def healthz():
        return {"ok": True}

    start_scheduler()
    return app


def parse_args() -> argparse.Namespace:
    load_dotenv(ENV_PATH)
    parser = argparse.ArgumentParser(description="Serve the Anyrouter status page.")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--debug", action="store_true", default=os.environ.get("FLASK_DEBUG") == "1")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
