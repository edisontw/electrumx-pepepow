#!/usr/bin/env python3

import argparse
import asyncio
import json
import os
import random
import subprocess
import sys
from typing import Optional, Tuple

from electrumx.lib.hash import hash_to_hex_str
from electrumx.server.db import DB
from electrumx.server.env import Env


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Verify ElectrumX DB headers hash against PEPEPOWd getblockhash "
            "without opening DB for serving."
        )
    )
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--db-dir", default="/var/lib/electrumx-pepepow")
    parser.add_argument("--coin", default="PEPEPOW")
    parser.add_argument("--net", default="mainnet")
    parser.add_argument("--cli", default="/home/ubuntu/PEPEPOW-cli")
    parser.add_argument("--datadir", default="/home/ubuntu/.PEPEPOWcore")
    parser.add_argument("--rpc-port", type=int, default=8000)
    parser.add_argument("--db-height", type=int, default=None)
    parser.add_argument(
        "--rpc-timeout",
        type=int,
        default=60,
        help="Timeout in seconds for electrumx_rpc getinfo.",
    )
    parser.add_argument(
        "--core-timeout",
        type=int,
        default=180,
        help="Timeout in seconds for PEPEPOW-cli getblockhash.",
    )
    return parser.parse_args()


def run_command(cmd, timeout: Optional[int] = None):
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"command timed out after {timeout}s: {' '.join(cmd)}"
        ) from exc
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        stdout = proc.stdout.strip()
        detail = stderr or stdout or f"exit code {proc.returncode}"
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{detail}")
    return proc.stdout.strip()


def get_db_height_from_rpc(rpc_port: int, timeout: int) -> int:
    cmd = [
        sys.executable,
        "-m",
        "electrumx.cli.electrumx_rpc",
        "-p",
        str(rpc_port),
        "getinfo",
    ]
    output = run_command(cmd, timeout=timeout)
    try:
        info = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"failed to parse electrumx_rpc getinfo output: {output}") from exc

    db_height = info.get("db height")
    if not isinstance(db_height, int) or db_height < 0:
        raise RuntimeError(f"invalid db height from electrumx_rpc: {db_height!r}")
    return db_height


def configure_env(args):
    os.environ["DB_DIRECTORY"] = args.db_dir
    os.environ["COIN"] = args.coin
    os.environ["NET"] = args.net
    os.environ["DAEMON_URL"] = ""
    os.environ.setdefault("SERVICES", "")
    os.environ.setdefault("REPORT_SERVICES", "")


def core_hash(height: int, cli_path: str, datadir: str, timeout: int) -> str:
    cmd = [cli_path, f"-datadir={datadir}", "getblockhash", str(height)]
    return run_command(cmd, timeout=timeout)


async def _read_header_via_api(db: DB, height: int) -> bytes:
    result = await db.read_headers(height, 1)
    if not (isinstance(result, tuple) and len(result) == 2):
        raise RuntimeError(f"unexpected read_headers return shape: {type(result)!r}")
    headers_concat, count = result
    if count != 1:
        raise RuntimeError(f"read_headers returned count={count} for height={height}")
    if not isinstance(headers_concat, (bytes, bytearray)):
        raise RuntimeError(f"unexpected header payload type: {type(headers_concat)!r}")
    return bytes(headers_concat)


def read_header_bytes(db: DB, height: int, db_height: int) -> bytes:
    if not (0 <= height <= db_height):
        raise ValueError(f"height out of range: {height}, expected [0, {db_height}]")

    api_error: Optional[Exception] = None
    if hasattr(db, "read_headers"):
        db.db_height = db_height
        try:
            header = asyncio.run(_read_header_via_api(db, height))
            expected_len = db.header_len(height)
            if len(header) != expected_len:
                raise RuntimeError(
                    f"read_headers returned {len(header)} bytes, expected {expected_len}"
                )
            return header
        except Exception as exc:
            api_error = exc

    offset = db.header_offset(height)
    expected_len = db.header_len(height)
    header = db.headers_file.read(offset, expected_len)
    if len(header) != expected_len:
        msg = (
            f"failed to read full header at height={height}: got {len(header)} bytes, "
            f"expected {expected_len}"
        )
        if api_error is not None:
            msg = f"{msg}; read_headers error: {api_error!r}"
        raise RuntimeError(msg)
    return header


def build_heights(db_height: int, samples: int, seed: int):
    rng = random.Random(seed)
    heights = [0, db_height // 2, db_height]
    for _ in range(samples):
        heights.append(rng.randint(0, db_height))
    return heights


def compare_hashes(
    db: DB,
    coin,
    db_height: int,
    heights,
    cli_path: str,
    datadir: str,
    core_timeout: int,
) -> Tuple[bool, Optional[Tuple[int, str, str]]]:
    mismatch = None
    for height in heights:
        header = read_header_bytes(db, height, db_height)
        electrum_hash = hash_to_hex_str(coin.header_hash_for_height(header, height))
        core_block_hash = core_hash(height, cli_path, datadir, core_timeout)

        print(f"Height {height}", flush=True)
        print(f"  ElectrumX: {electrum_hash}", flush=True)
        print(f"  Core     : {core_block_hash}", flush=True)

        if electrum_hash != core_block_hash:
            print("  MISMATCH", flush=True)
            mismatch = (height, electrum_hash, core_block_hash)
            break

    return mismatch is None, mismatch


def main():
    args = parse_args()
    if args.samples < 0:
        raise SystemExit("--samples must be >= 0")
    if args.db_height is not None and args.db_height < 0:
        raise SystemExit("--db-height must be >= 0")

    db_height = args.db_height
    if db_height is None:
        db_height = get_db_height_from_rpc(args.rpc_port, args.rpc_timeout)

    configure_env(args)
    env = Env()
    db = DB(env)

    heights = build_heights(db_height, args.samples, args.seed)

    print(f"DB height: {db_height}", flush=True)
    print(f"Tested heights: {heights}", flush=True)

    all_match, mismatch = compare_hashes(
        db=db,
        coin=env.coin,
        db_height=db_height,
        heights=heights,
        cli_path=args.cli,
        datadir=args.datadir,
        core_timeout=args.core_timeout,
    )

    if all_match:
        print("all_match=true", flush=True)
        return 0

    height, electrum_hash, core_block_hash = mismatch
    print("all_match=false", flush=True)
    print(f"first_mismatch_height={height}", flush=True)
    print(f"first_mismatch_electrumx={electrum_hash}", flush=True)
    print(f"first_mismatch_core={core_block_hash}", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
