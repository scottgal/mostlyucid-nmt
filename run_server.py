#!/usr/bin/env python3
"""Standalone entry point for MostlyLucid-NMT translation server.

This script provides a CLI interface for running the translation service,
designed to work both as a standalone executable and as a tool for LLM CLIs.

Usage:
    # Start server (default)
    python run_server.py

    # Direct translation (no server required - loads model on demand)
    python run_server.py translate "Hello world" --to de
    echo "Hello world" | python run_server.py translate --to de

    # Server mode
    python run_server.py server --port 8080
    python run_server.py server --background

    # MCP server mode (for LLM tool integration)
    python run_server.py mcp

    # Utilities
    python run_server.py languages
    python run_server.py status
"""

import argparse
import json
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Optional, List


def get_version() -> str:
    """Get version from package or return default."""
    try:
        from src import __version__
        return __version__
    except ImportError:
        return "4.0.0"


# =============================================================================
# Direct Translation (No Server Required)
# =============================================================================

def translate_direct(
    texts: List[str],
    source_lang: str,
    target_lang: str,
    model_family: Optional[str] = None
) -> List[str]:
    """Translate text directly without requiring a running server.

    This loads the model on-demand, which is slower for single translations
    but doesn't require managing a server process.
    """
    # Set model family if specified
    if model_family:
        os.environ["MODEL_FAMILY"] = model_family

    from src.services.model_manager import model_manager
    from src.config import config

    # Get the translation pipeline
    pipeline = model_manager.get_pipeline(source_lang, target_lang)

    # Translate
    results = pipeline(texts, max_length=512)

    # Extract translations
    if isinstance(results, list):
        return [r.get("translation_text", r) if isinstance(r, dict) else str(r) for r in results]
    return [str(results)]


def cmd_translate(args):
    """Handle the translate command."""
    # Get text from args or stdin
    if args.text:
        texts = [args.text] if isinstance(args.text, str) else args.text
    elif not sys.stdin.isatty():
        # Read from stdin
        stdin_text = sys.stdin.read().strip()
        if not stdin_text:
            print(json.dumps({"error": "No text provided"}), file=sys.stderr)
            return 1
        texts = [stdin_text]
    else:
        print(json.dumps({"error": "No text provided. Use --text or pipe via stdin"}), file=sys.stderr)
        return 1

    # Check if server is running - use it if available for better performance
    if check_server(args.host, args.port):
        try:
            result = translate_via_server(texts, args.source, args.to, args.host, args.port)
            output_result(result, args.json)
            return 0
        except Exception:
            pass  # Fall back to direct translation

    # Direct translation (loads model)
    try:
        if not args.json:
            print(f"Loading model ({args.model or 'opus-mt'})...", file=sys.stderr)

        translations = translate_direct(texts, args.source, args.to, args.model)

        if args.json:
            print(json.dumps({
                "source": texts,
                "translated": translations,
                "source_lang": args.source,
                "target_lang": args.to
            }))
        else:
            for t in translations:
                print(t)
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1


# =============================================================================
# Server Mode
# =============================================================================

def check_server(host: str = "127.0.0.1", port: int = 8000) -> bool:
    """Check if server is running and ready."""
    try:
        import httpx
        response = httpx.get(f"http://{host}:{port}/readyz", timeout=2.0)
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


def translate_via_server(
    texts: List[str],
    source_lang: str,
    target_lang: str,
    host: str = "127.0.0.1",
    port: int = 8000
) -> dict:
    """Translate via running server."""
    import httpx

    response = httpx.post(
        f"http://{host}:{port}/translate",
        json={
            "text": texts,
            "source_lang": source_lang,
            "target_lang": target_lang
        },
        timeout=120.0
    )
    return response.json()


def output_result(result: dict, as_json: bool):
    """Output translation result."""
    if as_json:
        print(json.dumps(result))
    else:
        if "translated" in result:
            for t in result["translated"]:
                print(t)
        elif "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
        else:
            print(json.dumps(result))


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
    script = f'''
import uvicorn
uvicorn.run("src.app:app", host="{host}", port={port}, log_level="warning")
'''

    if sys.platform == "win32":
        process = subprocess.Popen(
            [sys.executable, "-c", script],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.getcwd()
        )
    else:
        process = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=os.getcwd()
        )

    return process.pid


def cmd_server(args):
    """Handle the server command."""
    if args.background:
        pid = run_background(args.host, args.port)
        print(f"Server started in background (PID: {pid})")
        print("Waiting for server to be ready...")

        if wait_for_server(args.host, args.port, timeout=120):
            print(f"Server ready at http://{args.host}:{args.port}")
            return 0
        else:
            print("Warning: Server may still be starting up", file=sys.stderr)
            return 0

    print(f"Starting MostlyLucid-NMT v{get_version()}")
    print(f"Server: http://{args.host}:{args.port}")
    print(f"Docs:   http://{args.host}:{args.port}/docs")
    print("Press Ctrl+C to stop")

    try:
        run_server(args.host, args.port, args.workers, args.reload)
    except KeyboardInterrupt:
        print("\nShutting down...")
    return 0


# =============================================================================
# MCP Server Mode (Model Context Protocol for LLM Tools)
# =============================================================================

def cmd_mcp(args):
    """Run as MCP (Model Context Protocol) server for LLM tool integration."""
    import asyncio

    async def run_mcp_server():
        """Run the MCP server using stdio transport."""
        try:
            from mcp.server import Server
            from mcp.server.stdio import stdio_server
            from mcp import types
        except ImportError:
            print(json.dumps({
                "error": "MCP not installed",
                "hint": "Install with: pip install mcp"
            }), file=sys.stderr)
            return 1

        server = Server("mostlylucid-nmt")

        @server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return [
                types.Tool(
                    name="translate",
                    description="Translate text between languages using neural machine translation",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Text to translate"
                            },
                            "source_lang": {
                                "type": "string",
                                "description": "Source language code (e.g., 'en', 'de', 'fr')",
                                "default": "en"
                            },
                            "target_lang": {
                                "type": "string",
                                "description": "Target language code (e.g., 'de', 'fr', 'es')"
                            }
                        },
                        "required": ["text", "target_lang"]
                    }
                ),
                types.Tool(
                    name="detect_language",
                    description="Detect the language of given text",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Text to analyze"
                            }
                        },
                        "required": ["text"]
                    }
                ),
                types.Tool(
                    name="list_languages",
                    description="List available languages for translation",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]

        @server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            if name == "translate":
                text = arguments.get("text", "")
                source = arguments.get("source_lang", "en")
                target = arguments.get("target_lang", "de")

                try:
                    # Try server first, fall back to direct
                    if check_server():
                        result = translate_via_server([text], source, target)
                        translation = result.get("translated", [text])[0]
                    else:
                        translations = translate_direct([text], source, target)
                        translation = translations[0]

                    return [types.TextContent(type="text", text=translation)]
                except Exception as e:
                    return [types.TextContent(type="text", text=f"Translation error: {e}")]

            elif name == "detect_language":
                text = arguments.get("text", "")
                try:
                    from langdetect import detect
                    lang = detect(text)
                    return [types.TextContent(type="text", text=lang)]
                except Exception as e:
                    return [types.TextContent(type="text", text=f"Detection error: {e}")]

            elif name == "list_languages":
                from src.config import config
                langs = config.get_supported_langs()
                return [types.TextContent(
                    type="text",
                    text=f"Supported languages ({config.MODEL_FAMILY}): {', '.join(sorted(langs))}"
                )]

            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

        return 0

    return asyncio.run(run_mcp_server())


# =============================================================================
# Utility Commands
# =============================================================================

def cmd_languages(args):
    """List available languages."""
    from src.config import config

    langs = sorted(config.get_supported_langs())

    if args.json:
        print(json.dumps({
            "model_family": config.MODEL_FAMILY,
            "languages": langs,
            "count": len(langs)
        }))
    else:
        print(f"Model: {config.MODEL_FAMILY}")
        print(f"Languages ({len(langs)}): {', '.join(langs)}")
    return 0


def cmd_status(args):
    """Check server status."""
    info = {"running": False, "host": args.host, "port": args.port}

    if check_server(args.host, args.port):
        info["running"] = True
        try:
            import httpx
            health = httpx.get(f"http://{args.host}:{args.port}/healthz", timeout=5.0)
            if health.status_code == 200:
                info["health"] = health.json()

            cache = httpx.get(f"http://{args.host}:{args.port}/cache", timeout=5.0)
            if cache.status_code == 200:
                info["cache"] = cache.json()
        except Exception as e:
            info["error"] = str(e)

    if args.json:
        print(json.dumps(info, indent=2))
    else:
        if info["running"]:
            print(f"Server running at http://{args.host}:{args.port}")
            if "cache" in info:
                c = info["cache"]
                print(f"  Models cached: {c.get('size', 0)}/{c.get('capacity', 0)}")
        else:
            print(f"Server not running at http://{args.host}:{args.port}")

    return 0 if info["running"] else 1


def cmd_info(args):
    """Show configuration info."""
    from src.config import config

    # Determine device string
    device = config.DEVICE_ENV
    if device == "auto":
        device = "GPU" if config.USE_GPU in ("1", "true", "yes") else "CPU (auto)"

    info = {
        "version": get_version(),
        "model_family": config.MODEL_FAMILY,
        "device": device,
        "batch_size": config.EASYNMT_BATCH_SIZE,
        "max_cached_models": config.MAX_CACHED_MODELS,
        "chunk_cache": {
            "enabled": config.CHUNK_CACHE_ENABLED,
            "capacity": config.CHUNK_CACHE_CAPACITY,
            "max_age_seconds": config.CHUNK_CACHE_MAX_AGE
        }
    }
    print(json.dumps(info, indent=2))
    return 0


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        prog="mostlylucid-nmt",
        description="Neural Machine Translation - CLI and Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Direct translation (loads model on demand)
  %(prog)s translate "Hello world" --to de
  echo "Bonjour" | %(prog)s translate --to en

  # Server mode (faster for multiple translations)
  %(prog)s server
  %(prog)s server --background

  # MCP mode (for LLM tool integration)
  %(prog)s mcp

  # Utilities
  %(prog)s languages
  %(prog)s status
  %(prog)s info

Environment Variables:
  MODEL_FAMILY          opus-mt, mbart50, or m2m100 (default: opus-mt)
  USE_GPU               Enable GPU acceleration (default: auto-detect)
  MODEL_CACHE_DIR       Directory for caching downloaded models
"""
    )
    parser.add_argument("--version", "-v", action="version", version=f"%(prog)s {get_version()}")
    parser.add_argument("--json", "-j", action="store_true", help="JSON output")
    parser.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Server port (default: 8000)")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # translate command
    p_translate = subparsers.add_parser("translate", aliases=["t"], help="Translate text")
    p_translate.add_argument("text", nargs="?", help="Text to translate (or pipe via stdin)")
    p_translate.add_argument("--to", "-t", required=True, help="Target language code")
    p_translate.add_argument("--source", "-s", default="en", help="Source language (default: en)")
    p_translate.add_argument("--model", "-m", help="Model family: opus-mt, mbart50, m2m100")
    p_translate.add_argument("--json", "-j", action="store_true", help="JSON output")
    p_translate.add_argument("--host", default="127.0.0.1", help=argparse.SUPPRESS)
    p_translate.add_argument("--port", "-p", type=int, default=8000, help=argparse.SUPPRESS)
    p_translate.set_defaults(func=cmd_translate)

    # server command
    p_server = subparsers.add_parser("server", aliases=["s"], help="Start translation server")
    p_server.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    p_server.add_argument("--port", "-p", type=int, default=8000, help="Port (default: 8000)")
    p_server.add_argument("--workers", "-w", type=int, default=1, help="Workers (default: 1)")
    p_server.add_argument("--reload", action="store_true", help="Auto-reload for development")
    p_server.add_argument("--background", "-b", action="store_true", help="Run in background")
    p_server.set_defaults(func=cmd_server)

    # mcp command
    p_mcp = subparsers.add_parser("mcp", help="Run as MCP server (for LLM tool integration)")
    p_mcp.set_defaults(func=cmd_mcp)

    # languages command
    p_langs = subparsers.add_parser("languages", aliases=["langs", "l"], help="List available languages")
    p_langs.add_argument("--json", "-j", action="store_true", help="JSON output")
    p_langs.set_defaults(func=cmd_languages)

    # status command
    p_status = subparsers.add_parser("status", help="Check server status")
    p_status.add_argument("--host", default="127.0.0.1", help=argparse.SUPPRESS)
    p_status.add_argument("--port", "-p", type=int, default=8000, help=argparse.SUPPRESS)
    p_status.add_argument("--json", "-j", action="store_true", help="JSON output")
    p_status.set_defaults(func=cmd_status)

    # info command
    p_info = subparsers.add_parser("info", help="Show configuration")
    p_info.set_defaults(func=cmd_info)

    args = parser.parse_args()

    # Default to server if no command given
    if not args.command:
        args.func = cmd_server
        args.background = False
        args.workers = 1
        args.reload = False

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
