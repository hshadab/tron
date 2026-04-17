"""Entry point for the Web UI demo. Usage: python run_ui.py"""

import asyncio
import multiprocessing
import os
import sys
import time
import webbrowser

import uvicorn
from dotenv import load_dotenv

load_dotenv()

UI_SERVER_PORT = 8400


def _check_env() -> None:
    """Validate required environment variables."""
    missing = []
    for var in (
        "ICME_API_KEY",
        "ICME_POLICY_ID",
        "TRON_PRIVATE_KEY",
        "TRON_WALLET_ADDRESS",
        "VENDOR_ADDRESS",
        "FACILITATOR_PRIVATE_KEY",
    ):
        if not os.getenv(var):
            missing.append(var)
    if missing:
        print(f"ERROR: Missing env vars: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in the values.")
        sys.exit(1)


def _run_facilitator() -> None:
    """Run the facilitator server in a subprocess."""
    from src.config import FACILITATOR_PRIVATE_KEY, FACILITATOR_SERVER_PORT

    os.environ["TRON_PRIVATE_KEY"] = FACILITATOR_PRIVATE_KEY
    from src.facilitator_server import create_facilitator_app

    app = create_facilitator_app()
    uvicorn.run(app, host="127.0.0.1", port=FACILITATOR_SERVER_PORT, log_level="warning")


def _run_vendor() -> None:
    """Run the vendor server in a subprocess."""
    from src.config import VENDOR_SERVER_PORT
    from src.vendor_server import create_vendor_app

    app = create_vendor_app()
    uvicorn.run(app, host="127.0.0.1", port=VENDOR_SERVER_PORT, log_level="warning")


def _run_ui() -> None:
    """Run the UI server."""
    from src.ui_server import create_ui_app

    app = create_ui_app()
    uvicorn.run(app, host="127.0.0.1", port=UI_SERVER_PORT, log_level="info")


def main() -> None:
    _check_env()

    print("Starting Preflight x TRON Web UI Demo...")
    print(f"  Facilitator server: http://127.0.0.1:8403")
    print(f"  Vendor server:      http://127.0.0.1:8402")
    print(f"  UI server:          http://127.0.0.1:{UI_SERVER_PORT}")

    facilitator_proc = multiprocessing.Process(target=_run_facilitator, daemon=True)
    facilitator_proc.start()

    vendor_proc = multiprocessing.Process(target=_run_vendor, daemon=True)
    vendor_proc.start()

    time.sleep(3)
    print("  x402 servers started.")

    # Open browser after a short delay
    def _open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://127.0.0.1:{UI_SERVER_PORT}")

    opener = multiprocessing.Process(target=_open_browser, daemon=True)
    opener.start()

    try:
        _run_ui()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        if facilitator_proc.is_alive():
            facilitator_proc.terminate()
        if vendor_proc.is_alive():
            vendor_proc.terminate()


if __name__ == "__main__":
    main()
