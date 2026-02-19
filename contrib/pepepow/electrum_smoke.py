#!/usr/bin/env python3

import argparse
import json
import socket
import subprocess
from decimal import Decimal
from hashlib import sha256

from electrumx.lib.coins import Pepepow


class ElectrumClient:
    def __init__(self, host: str, port: int, timeout: float = 15.0):
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.settimeout(timeout)
        self._file = self._sock.makefile("rwb")
        self._next_id = 1

    def close(self):
        try:
            self._file.close()
        finally:
            self._sock.close()

    def request(self, method: str, params, *, expect_error: bool = False):
        req_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        self._file.write((json.dumps(payload) + "\n").encode("utf-8"))
        self._file.flush()

        line = self._file.readline()
        if not line:
            raise RuntimeError(f"no response for {method}")
        resp = json.loads(line.decode("utf-8"))
        if resp.get("id") != req_id:
            raise RuntimeError(f"id mismatch for {method}: {resp}")
        if resp.get("error") is not None:
            if expect_error:
                return resp
            raise RuntimeError(f"{method} returned error: {resp['error']}")
        if expect_error:
            raise RuntimeError(f"{method} unexpectedly succeeded: {resp.get('result')}")
        return resp


def run_cli_json(cli_path: str, datadir: str, *args):
    cmd = [cli_path, f"-datadir={datadir}", *args]
    out = subprocess.check_output(cmd, text=True, timeout=20).strip()
    if out and out[0] in "{[":
        return json.loads(out)
    if out in ("true", "false", "null"):
        return json.loads(out)
    if out and out[0] == '"':
        return json.loads(out)
    return out


def satoshis(value):
    return int((Decimal(str(value)) * Decimal(100_000_000)).to_integral_value())


def address_to_scripthash(address: str) -> str:
    script = Pepepow.pay_to_address_script(address)
    return sha256(script).digest()[::-1].hex()


def main():
    parser = argparse.ArgumentParser(description="PEPEPOW Electrum protocol smoke checker")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=50001)
    parser.add_argument("--address", default="PGZrJkuJU39AqPfJQ2Rcpng9ChLwgybMHh")
    parser.add_argument("--cli", default="/home/ubuntu/PEPEPOW-cli")
    parser.add_argument("--datadir", default="/home/ubuntu/.PEPEPOWcore")
    args = parser.parse_args()

    scripthash = address_to_scripthash(args.address)
    cli = lambda *rpc_args: run_cli_json(args.cli, args.datadir, *rpc_args)

    client = ElectrumClient(args.host, args.port)
    try:
        server_version = client.request("server.version", ["pepepow-smoke", "1.4"])["result"]
        headers_sub = client.request("blockchain.headers.subscribe", [])["result"]
        balance = client.request("blockchain.scripthash.get_balance", [scripthash])["result"]
        listunspent = client.request("blockchain.scripthash.listunspent", [scripthash])["result"]
        history = client.request("blockchain.scripthash.get_history", [scripthash])["result"]

        if not listunspent and not history:
            raise RuntimeError("expected at least one listunspent/history entry for smoke address")

        txid = None
        if history:
            txid = history[0]["tx_hash"]
        elif listunspent:
            txid = listunspent[0]["tx_hash"]
        else:
            txid = "875791bbe84fa3fa3dce818296832837ee452b1f2986eb50e22142afebe2a1aa"

        tx_raw = client.request("blockchain.transaction.get", [txid])["result"]
        if not isinstance(tx_raw, str) or not tx_raw:
            raise RuntimeError("blockchain.transaction.get returned invalid payload")

        tx_broadcast_err = client.request(
            "blockchain.transaction.broadcast",
            ["00"],
            expect_error=True,
        )["error"]

        confirmed_from_utxos = 0
        for utxo in listunspent:
            txout = cli("gettxout", utxo["tx_hash"], str(utxo["tx_pos"]), "true")
            if not isinstance(txout, dict):
                raise RuntimeError(f"missing core txout for {utxo['tx_hash']}:{utxo['tx_pos']}")
            script_hex = txout.get("scriptPubKey", {}).get("hex")
            if not script_hex:
                raise RuntimeError(f"missing scriptPubKey for {utxo['tx_hash']}:{utxo['tx_pos']}")

            expected_scripthash = sha256(bytes.fromhex(script_hex)).digest()[::-1].hex()
            if expected_scripthash != scripthash:
                raise RuntimeError(
                    f"scripthash mismatch for {utxo['tx_hash']}:{utxo['tx_pos']} "
                    f"{expected_scripthash} != {scripthash}"
                )

            core_value = satoshis(txout["value"])
            if core_value != utxo["value"]:
                raise RuntimeError(
                    f"value mismatch for {utxo['tx_hash']}:{utxo['tx_pos']} "
                    f"{core_value} != {utxo['value']}"
                )
            confirmed_from_utxos += utxo["value"]

        if confirmed_from_utxos != balance["confirmed"]:
            raise RuntimeError(
                f"confirmed balance mismatch: {confirmed_from_utxos} != {balance['confirmed']}"
            )

        output = {
            "server_version": server_version,
            "headers_subscribe_height": headers_sub.get("height"),
            "scripthash": scripthash,
            "balance": balance,
            "listunspent_count": len(listunspent),
            "history_count": len(history),
            "transaction_get_txid": txid,
            "transaction_get_size": len(tx_raw) // 2,
            "broadcast_error": tx_broadcast_err,
            "core_crosscheck_confirmed_sats": confirmed_from_utxos,
        }
        print(json.dumps(output, indent=2, sort_keys=True))
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
