#!/usr/bin/env python3
"""
Simple launcher for the O2C Graph System backend.
Run from project root: python run_backend.py
"""

import argparse
import os
import socket
import sys

# Get project root directory
project_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_root)

# Add project root to Python path so imports work
sys.path.insert(0, project_root)


def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """Return True if a TCP port can be bound on the given host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def find_available_port(start_port: int, max_attempts: int = 20) -> int | None:
    """Find the first available port from start_port within max_attempts."""
    for offset in range(max_attempts):
        candidate = start_port + offset
        if is_port_available(candidate):
            return candidate
    return None

def parse_args() -> argparse.Namespace:
    """Parse CLI args for a clean, predictable startup flow."""
    parser = argparse.ArgumentParser(description="Start O2C backend server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", 8000)),
        help="Preferred port (auto-falls back if unavailable)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    return parser.parse_args()


def main() -> None:
    """Launch uvicorn with fallback port handling."""
    args = parse_args()

    import uvicorn
    from backend.main import app

    requested_port = args.port
    port = requested_port

    if not is_port_available(requested_port, host=args.host):
        fallback_port = find_available_port(requested_port + 1)
        if fallback_port is None:
            print(f"ERROR: Port {requested_port} is in use and no fallback port was found.")
            print("Set --port to a free port and retry, e.g. python run_backend.py --port 8010")
            sys.exit(1)

        port = fallback_port
        print(f"WARNING: Port {requested_port} is already in use. Switching to port {port}.")

    print(f"\n{'='*60}")
    print("Starting O2C Graph System Backend")
    print(f"API base URL: http://localhost:{port}")
    print(f"Health check: http://localhost:{port}/health")
    print(f"OpenAPI docs: http://localhost:{port}/docs")
    print(f"Reload mode: {'ON' if args.reload else 'OFF'}")
    print(f"{'='*60}\n")

    uvicorn.run(
        app,
        host=args.host,
        port=port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
