"""Start the complete ShieldPay LAN demo on Windows.

Run from the repository root with: py -3 start_demo.py
Existing chain/backend/Expo processes are reused when their ports are active.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
CHAIN_PORT = 8545
BACKEND_PORT = 8765
EXPO_PORT = 8081
STARTED: list[subprocess.Popen] = []
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def lan_ipv4() -> str:
    """Ask Windows routing which local IPv4 would reach an external network."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 80))  # UDP connect selects a route; sends no packet.
        address = probe.getsockname()[0]
        if address.startswith("127."):
            raise RuntimeError("No active LAN IPv4 route was found. Connect to Wi-Fi and retry.")
        return address
    finally:
        probe.close()


def launch(title: str, command: str, env: dict[str, str] | None = None) -> subprocess.Popen:
    print(f"Starting {title}: {command}", flush=True)
    proc = subprocess.Popen(
        ["cmd.exe", "/c", command], cwd=ROOT, env=env,
        creationflags=CREATE_NEW_CONSOLE,
    )
    STARTED.append(proc)
    return proc


def wait_for_port(port: int, title: str, timeout: int = 45) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_is_open(port):
            return
        time.sleep(0.5)
    raise RuntimeError(f"{title} did not open port {port} within {timeout} seconds.")


def rpc(method: str, params: list | None = None) -> object:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}).encode()
    request = Request("http://127.0.0.1:8545", data=body, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=3) as response:
        payload = json.load(response)
    if "error" in payload:
        raise RuntimeError(payload["error"].get("message", "Local chain RPC error"))
    return payload.get("result")


def wait_for_chain(timeout: int = 45) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            chain_id = rpc("eth_chainId")
            if chain_id != "0x7a69":  # Hardhat chain ID 31337
                raise RuntimeError(f"Port 8545 is occupied by chain ID {chain_id}, expected Hardhat 31337.")
            return
        except (OSError, URLError, TimeoutError):
            time.sleep(0.5)
    raise RuntimeError("Hardhat JSON-RPC did not become ready on 127.0.0.1:8545.")


def deployment_is_live() -> bool:
    config_file = ROOT / "backend" / "chain_config.json"
    if not config_file.exists():
        return False
    try:
        config = json.loads(config_file.read_text(encoding="utf-8"))
        address = config.get("contract_address") or config.get("address")
        if not address:
            return False
        code = rpc("eth_getCode", [address, "latest"])
        return isinstance(code, str) and code not in ("0x", "0x0")
    except (OSError, ValueError, URLError, TimeoutError, RuntimeError):
        return False


def wait_for_backend(timeout: int = 45) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{BACKEND_PORT}/health", timeout=2) as response:
                data = json.load(response)
            if data.get("ok"):
                if not data.get("blockchain", {}).get("connected"):
                    raise RuntimeError("Backend is running, but its local smart contract is not connected.")
                return
        except (OSError, URLError, TimeoutError, ValueError):
            time.sleep(0.5)
    raise RuntimeError("Backend did not become ready on port 8765.")


def main() -> int:
    if os.name != "nt":
        print("This launcher currently targets the Windows demo setup.", file=sys.stderr)
        return 2
    if not (ROOT / "node_modules" / ".bin" / "hardhat.cmd").exists():
        print("Dependencies are missing. From the project root run: npm.cmd install --legacy-peer-deps", file=sys.stderr)
        return 2

    try:
        if port_is_open(CHAIN_PORT):
            wait_for_chain(timeout=5)
            print("Reusing existing Hardhat node on 127.0.0.1:8545.")
        else:
            launch("Hardhat blockchain", "npm.cmd run chain:node")
            wait_for_chain()
            print("Hardhat chain 31337 is ready.")

        if deployment_is_live():
            print("Reusing the deployed ShieldPay escrow contract.")
        else:
            print("No live contract deployment found; deploying to the local chain.", flush=True)
            result = subprocess.run(
                ["cmd.exe", "/c", "npm.cmd run chain:deploy"], cwd=ROOT,
                check=False,
            )
            if result.returncode:
                raise RuntimeError(f"Contract deployment failed with exit code {result.returncode}.")
            if not deployment_is_live():
                raise RuntimeError("Deployment command finished, but no contract code was found at its configured address.")

        if port_is_open(BACKEND_PORT):
            wait_for_backend(timeout=5)
            print("Reusing existing backend on port 8765.")
        else:
            backend_env = os.environ.copy()
            backend_env.setdefault("SHIELDPAY_ESCROW_TIMEOUT_SECONDS", "30")
            launch("ShieldPay backend", f'"{sys.executable}" backend\\server.py', backend_env)
            wait_for_backend()
            print("Backend and escrow contract are connected.")

        ip = lan_ipv4()
        if port_is_open(EXPO_PORT):
            print("Expo port 8081 is already active; reusing it (restart Expo manually if its API URL is stale).")
        else:
            mobile_env = os.environ.copy()
            mobile_env["EXPO_PUBLIC_API_URL"] = f"http://{ip}:{BACKEND_PORT}"
            launch("Expo mobile app", "npx.cmd expo start --lan", mobile_env)
            wait_for_port(EXPO_PORT, "Expo Metro", timeout=90)

        print("\nShieldPay is ready:")
        print(f"  Dashboard: http://{ip}:{BACKEND_PORT}/dashboard")
        print(f"  Mobile API: http://{ip}:{BACKEND_PORT}")
        print(f"  Expo Go: scan the QR code in the Expo window (LAN {ip}:8081).")
        print("  Local chain: 127.0.0.1:8545 (keep this RPC off the LAN).")
        print("Press Ctrl+C here to stop only the processes this launcher started.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping processes started by this launcher...", flush=True)
        for proc in reversed(STARTED):
            if proc.poll() is None:
                proc.terminate()
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Startup failed: {exc}", file=sys.stderr)
        print("Existing processes are left untouched. Check their terminal windows and retry.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
