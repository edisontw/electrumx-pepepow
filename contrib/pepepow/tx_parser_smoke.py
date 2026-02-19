#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys

from electrumx.lib.hash import hash_to_hex_str
from electrumx.lib.tx_pepepow import DeserializerPepepow


DEFAULT_TXS = [
    ("regular", "875791bbe84fa3fa3dce818296832837ee452b1f2986eb50e22142afebe2a1aa"),
    ("consolidation", "d1db8fc2579bb1a7ec924bb22f6ac584662dea238c6504d15ba2181613740c51"),
    ("v2_complex", "f69826069c707a87eacdaaa4d684babaa50654f548e0e6ef94c35ee20e4d3c6a"),
]


def run_cli(cli_path, datadir, *args):
    cmd = [cli_path, f"-datadir={datadir}", *args]
    out = subprocess.check_output(cmd, text=True, timeout=20).strip()
    if out and out[0] in "{[":
        return json.loads(out)
    return out


def main():
    parser = argparse.ArgumentParser(description="PEPEPOW tx parser smoke checker")
    parser.add_argument("--cli", default="/home/ubuntu/PEPEPOW-cli")
    parser.add_argument("--datadir", default="/home/ubuntu/.PEPEPOWcore")
    parser.add_argument(
        "--txid",
        action="append",
        default=[],
        help="Custom txid(s). If provided, labels are auto-generated.",
    )
    args = parser.parse_args()

    txs = DEFAULT_TXS
    if args.txid:
        txs = [(f"custom_{idx+1}", txid) for idx, txid in enumerate(args.txid)]

    for label, txid in txs:
        try:
            raw_hex = run_cli(args.cli, args.datadir, "getrawtransaction", txid, "0")
            raw_tx = bytes.fromhex(raw_hex)
            deser = DeserializerPepepow(raw_tx)
            tx = deser.read_tx()
            parsed_txid = hash_to_hex_str(tx.txid)

            if parsed_txid != txid:
                raise RuntimeError(f"txid mismatch for {label}: {parsed_txid} != {txid}")
            if deser.cursor != len(raw_tx):
                raise RuntimeError(
                    f"cursor did not consume full tx for {label}: "
                    f"{deser.cursor} != {len(raw_tx)}"
                )

            result = {
                "label": label,
                "txid": txid,
                "version": tx.version,
                "vin": len(tx.inputs),
                "vout": len(tx.outputs),
                "size": len(raw_tx),
            }
            print(json.dumps(result, sort_keys=True))
        except Exception as exc:
            print(f"ERROR: parser smoke failed for {label} ({txid}): {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
