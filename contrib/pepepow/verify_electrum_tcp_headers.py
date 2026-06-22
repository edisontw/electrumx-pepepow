#!/usr/bin/env python3
"""Verify PEPEPOW Electrum TCP block headers against PEPEPOW Core.

This script asks ElectrumX for raw headers through the Electrum protocol method
``blockchain.block.header`` and compares the PEPEPOW-specific header hash with
``PEPEPOW-cli getblockhash``.

Important: PEPEPOW block hashes are not Bitcoin-style double-SHA256 hashes. Use
``coin.header_hash_for_height(header, height)`` so the correct PEPEPOW era-specific
hashing path is used.
"""

import argparse
import json
import os
import random
import socket
import subprocess
import sys
from typing import Iterable, List, Optional, Sequence, Tuple

from electrumx.lib.hash import hash_to_hex_str
from electrumx.server.env import Env


DEFAULT_CLI = "/home/ubuntu/PEPEPOW-cli"
DEFAULT_DATADIR = "/home/ubuntu/.PEPEPOWcore"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Electrum TCP headers against PEPEPOWd getblockhash."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Electrum TCP host")
    parser.add_argument("--port", type=int, default=50001, help="Electrum TCP port")
    parser.add_argument("--cli", default=DEFAULT_CLI, help="Path to PEPEPOW-cli")
    parser.add_argument("--datadir", default=DEFAULT_DATADIR, help="PEPEPOW datadir")
    parser.add_argument("--samples", type=int, default=10, help="Random sample count")
    parser.add_argument("--seed", type=int, default=0, help="Random seed")
    parser.add_argument(
        "--height",
        action="append",
        type=int,
        default=[],
        help="Specific height to check. Can be repeated.",
    )
    parser.add_argument(
        "--include-fixed",
        action="store_true",
        help="Also check common fixed heights around PEPEPOW hash eras.",
    )
    parser.add_argument(
        "--tip-margin",
        type=int,
        default=20,
        help="Do not randomly sample the newest N blocks.",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="Socket timeout")
    parser.add_argument("--coin", default="PEPEPOW", help="ElectrumX COIN value")
    parser.add_argument("--net", default="mainnet", help="ElectrumX NET value")
    return parser.parse_args()


def run_command(cmd: Sequence[str], timeout: Optional[int] = None) -> str:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{detail}")
    return proc.stdout.strip()


def core_tip(cli_path: str, datadir: str) -> int:
    return int(run_command([cli_path, f"-datadir={datadir}", "getblockcount"], timeout=60))


def core_hash(cli_path: str, datadir: str, height: int) -> str:
    return run_command(
        [cli_path, f"-datadir={datadir}", "getblockhash", str(height)], timeout=120
    )


def electrum_request(host: str, port: int, request: dict, timeout: float) -> dict:
    payload = json.dumps(request, separators=(",", ":")) + "\n"
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)

        # Electrum protocol servers may require server.version as the first
        # message on a connection. Send it and read the response before the
        # actual header request.
        hello = {
            "id": "version",
            "method": "server.version",
            "params": ["pepepow-header-verifier", "1.4"],
        }
        sock.sendall((json.dumps(hello, separators=(",", ":")) + "\n").encode())
        _read_json_line(sock)

        sock.sendall(payload.encode())
        return _read_json_line(sock)


def _read_json_line(sock: socket.socket) -> dict:
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(65536)
        if not chunk:
            break
        data += chunk
    if not data:
        raise RuntimeError("empty response from Electrum TCP server")
    line = data.split(b"\n", 1)[0].decode().strip()
    try:
        return json.loads(line)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON response: {line}") from exc


def electrum_header(host: str, port: int, height: int, timeout: float) -> bytes:
    response = electrum_request(
        host,
        port,
        {"id": height, "method": "blockchain.block.header", "params": [height]},
        timeout,
    )
    if response.get("error"):
        raise RuntimeError(f"Electrum error at height {height}: {response['error']}")
    header_hex = response.get("result")
    if not isinstance(header_hex, str) or not header_hex:
        raise RuntimeError(f"missing header result at height {height}: {response}")
    return bytes.fromhex(header_hex)


def build_heights(tip: int, samples: int, seed: int, margin: int, fixed: bool, heights: List[int]) -> List[int]:
    selected = list(heights)
    if fixed:
        selected.extend([1, 1000, 1930000, 1930001, 4380117, 4380118, tip - 100, tip - margin])
    max_height = tip - margin
    if max_height <= 1:
        raise RuntimeError(f"invalid sampling range: tip={tip}, margin={margin}")
    rng = random.Random(seed)
    selected.extend(rng.randint(1, max_height) for _ in range(samples))

    deduped: List[int] = []
    seen = set()
    for height in selected:
        if 0 <= height <= tip and height not in seen:
            deduped.append(height)
            seen.add(height)
    return deduped


def configure_env(coin: str, net: str) -> Env:
    os.environ["COIN"] = coin
    os.environ["NET"] = net
    os.environ.setdefault("DAEMON_URL", "")
    os.environ.setdefault("DB_DIRECTORY", "/var/lib/electrumx-pepepow")
    os.environ.setdefault("SERVICES", "")
    os.environ.setdefault("REPORT_SERVICES", "")
    return Env()


def verify_heights(args: argparse.Namespace, env: Env, heights: Iterable[int]) -> Tuple[int, int]:
    checked = 0
    failures = 0
    for height in heights:
        header = electrum_header(args.host, args.port, height, args.timeout)
        electrum_hash = hash_to_hex_str(env.coin.header_hash_for_height(header, height))
        daemon_hash = core_hash(args.cli, args.datadir, height)
        checked += 1

        if electrum_hash == daemon_hash:
            print(f"OK   height={height} hash={daemon_hash}", flush=True)
        else:
            failures += 1
            print(f"FAIL height={height}", flush=True)
            print(f"     electrum_hash={electrum_hash}", flush=True)
            print(f"     daemon_hash  ={daemon_hash}", flush=True)
            print(f"     header_hex   ={header.hex()}", flush=True)
    return checked, failures


def main() -> int:
    args = parse_args()
    if args.samples < 0:
        raise SystemExit("--samples must be >= 0")
    if not os.path.exists(args.cli):
        raise SystemExit(f"PEPEPOW-cli not found: {args.cli}")

    env = configure_env(args.coin, args.net)
    tip = core_tip(args.cli, args.datadir)
    heights = build_heights(
        tip=tip,
        samples=args.samples,
        seed=args.seed,
        margin=args.tip_margin,
        fixed=args.include_fixed,
        heights=args.height,
    )

    print(f"daemon_tip={tip}", flush=True)
    print(f"electrum_tcp={args.host}:{args.port}", flush=True)
    print(f"tested_heights={heights}", flush=True)

    checked, failures = verify_heights(args, env, heights)

    print(f"checked={checked}", flush=True)
    print(f"failures={failures}", flush=True)
    if failures:
        print("all_match=false", flush=True)
        return 2

    print("all_match=true", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
