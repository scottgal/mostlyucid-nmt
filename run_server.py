#!/usr/bin/env python3
"""Standalone entry point for MostlyLucid-NMT translation server.

This script provides a CLI interface for running the translation service,
designed to work both as a standalone executable and as a tool for LLM CLIs.

Usage:
    # Start server (default)
    python run_server.py

    # Start with custom port
    python run_server.py --port 8080

    # Start in background mode (for LLM tool integration)
    python run_server.py --background

    # Check if server is ready
    python run_server.py --check

    # Show configuration
    python run_server.py --info

    # Translate text directly (one-shot mode for LLM tools)
    python run_server.py --translate "Hello world" --source en --target de
"""

import argparse
import json
import os
import sys
import time
import signal
import subprocess
from pathlib import Path


def get_version() -> str:
    """Get version from package or return default."""
    try:
        from src import __version__
        return __version__
    except ImportError:
        return "3.2.0"


def check_server(host: str = "127.0.0.1", port: int = 8000) -> bool:
    """Check if server is running and ready."""
    try:
        import httpx
        response = httpx.get(f"http://{host}:{port}/readyz", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False


def wait_for_server(host: str = "127.0.0.1", port: int = 8000, timeout: int = 120) -> bool:
    """Wait for server to become ready."""
    start = time.time()
    while time.time() - start < timeout:
        if check_server(host, port):
            return True
        time.sleep(1)
    return False


def translate_oneshot(
    text: str,
    source_lang: str,
    target_lang: str,
    host: str = "127.0.0.1",
    port: int = 8000
) -> dict:
    """Perform a one-shot translation via the API."""
    import httpx

    response = httpx.post(
        f"http://{host}:{port}/translate",
        json={
            "text": [text] if isinstance(text, str) else text,
            "source_lang": source_lang,
            "target_lang": target_lang
        },
        timeout=60.0
    )
    return response.json()


def get_server_info(host: str = "127.0.0.1", port: int = 8000) -> dict:
    """Get server status and configuration."""
    import httpx

    info = {"running": False}

    try:
        health = httpx.get(f"http://{host}:{port}/healthz", timeout=5.0)
        if health.status_code == 200:
            info["running"] = True
            info["health"] = health.json()

        cache = httpx.get(f"http://{host}:{port}/cache", timeout=5.0)
        if cache.status_code == 200:
            info["cache"] = cache.json()

        chunk_cache = httpx.get(f"http://{host}:{port}/chunk_cache", timeout=5.0)
        if chunk_cache.status_code == 200:
            info["chunk_cache"] = chunk_cache.json()
    except Exception as e:
        info["error"] = str(e)

    return info


def print_config_info():
    """Print current configuration."""
    from src.config import config

    info = {
        "version": get_version(),
        "model_family": config.MODEL_FAMILY,
        "device": config.DEVICE if config.DEVICE else ("GPU" if config.USE_GPU else "CPU"),
        "batch_size": config.EASYNMT_BATCH_SIZE,
        "max_cached_models": config.MAX_CACHED_MODELS,
        "chunk_cache": {
            "enabled": config.CHUNK_CACHE_ENABLED,
            "capacity": config.CHUNK_CACHE_CAPACITY,
            "max_age_seconds": config.CHUNK_CACHE_MAX_AGE
        },
        "queue": {
            "enabled": config.ENABLE_QUEUE,
            "max_size": config.MAX_QUEUE_SIZE,
            "max_inflight": config.MAX_INFLIGHT_TRANSLATIONS
        }
    }
    print(json.dumps(info, indent=2))


def run_server(host: str, port: int, workers: int, reload: bool):
    """Run the uvicorn server."""
    import uvicorn

    uvicorn.run(
        "src.app:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload,
        log_level="info"
    )


def run_background(host: str, port: int) -> int:
    """Start server in background and return PID."""
    # Create a simple script to run in background
    script = f'''
import uvicorn
uvicorn.run("src.app:app", host="{host}", port={port}, log_level="warning")
'''

    if sys.platform == "win32":
        # Windows: use subprocess with CREATE_NEW_PROCESS_GROUP
        process = subprocess.Popen(
            [sys.executable, "-c", script],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd()
        )
    else:
        # Unix: use nohup-style background
        process = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=os.getcwd()
        )

    return process.pid


def main():
    parser = argparse.ArgumentParser(
        description="MostlyLucid-NMT Translation Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           Start server on default port 8000
  %(prog)s --port 8080               Start on custom port
  %(prog)s --check                   Check if server is ready
  %(prog)s --info                    Show configuration
  %(prog)s --translate "Hello" -s en -t de   Translate text (requires running server)
  %(prog)s --background              Start server in background

Environment Variables:
  MODEL_FAMILY          Model to use: opus-mt, mbart50, m2m100 (default: opus-mt)
  USE_GPU               Enable GPU acceleration (default: auto-detect)
  EASYNMT_BATCH_SIZE    Batch size for translation (default: 8)
  CHUNK_CACHE_ENABLED   Enable chunk translation cache (default: 1)
"""
    )

    # Server options
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--workers", "-w", type=int, default=1, help="Number of workers (default: 1)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--background", "-b", action="store_true", help="Run server in background")

    # Status/info options
    parser.add_argument("--check", "-c", action="store_true", help="Check if server is ready")
    parser.add_argument("--info", "-i", action="store_true", help="Show configuration info")
    parser.add_argument("--status", action="store_true", help="Get running server status")
    parser.add_argument("--version", "-v", action="store_true", help="Show version")

    # Translation options (for LLM tool integration)
    parser.add_argument("--translate", "-T", type=str, help="Text to translate (one-shot mode)")
    parser.add_argument("--source", "-s", type=str, default="en", help="Source language (default: en)")
    parser.add_argument("--target", "-t", type=str, default="de", help="Target language (default: de)")
    parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    # Handle version
    if args.version:
        print(f"MostlyLucid-NMT v{get_version()}")
        return 0

    # Handle info
    if args.info:
        print_config_info()
        return 0

    # Handle check
    if args.check:
        ready = check_server(args.host, args.port)
        if args.json:
            print(json.dumps({"ready": ready, "host": args.host, "port": args.port}))
        else:
            print("ready" if ready else "not ready")
        return 0 if ready else 1

    # Handle status
    if args.status:
        info = get_server_info(args.host, args.port)
        print(json.dumps(info, indent=2))
        return 0 if info.get("running") else 1

    # Handle one-shot translation
    if args.translate:
        if not check_server(args.host, args.port):
            if args.json:
                print(json.dumps({"error": "Server not running", "hint": "Start with: run_server.py"}))
            else:
                print("Error: Server not running. Start with: run_server.py", file=sys.stderr)
            return 1

        try:
            result = translate_oneshot(
                args.translate,
                args.source,
                args.target,
                args.host,
                args.port
            )
            if args.json:
                print(json.dumps(result))
            else:
                # Extract just the translated text for clean output
                if "translated" in result:
                    translations = result["translated"]
                    for t in translations:
                        print(t)
                else:
                    print(json.dumps(result))
        except Exception as e:
            if args.json:
                print(json.dumps({"error": str(e)}))
            else:
                print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    # Handle background mode
    if args.background:
        pid = run_background(args.host, args.port)
        print(f"Server started in background (PID: {pid})")
        print(f"Waiting for server to be ready...")

        if wait_for_server(args.host, args.port, timeout=120):
            print(f"Server ready at http://{args.host}:{args.port}")
            return 0
        else:
            print("Warning: Server may still be starting up", file=sys.stderr)
            return 0

    # Default: run server in foreground
    print(f"Starting MostlyLucid-NMT v{get_version()}")
    print(f"Server will be available at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop")

    try:
        run_server(args.host, args.port, args.workers, args.reload)
    except KeyboardInterrupt:
        print("\nShutting down...")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
