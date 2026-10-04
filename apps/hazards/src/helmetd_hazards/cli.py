import argparse
import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from .network import KINDS, RPC_URL, WALLET, Network, clear, explorer, nearby, report, wallet
from .voice_tools import POSITION


def main():
    load_dotenv(".env")
    parser = argparse.ArgumentParser(description="Share road hazards with trusted riders on devnet")
    parser.add_argument("--wallet", type=Path, default=WALLET)
    parser.add_argument("--rpc", default=os.getenv("HELMETD_SOLANA_RPC", RPC_URL))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create a local test wallet; show its public address")
    pos = commands.add_parser("demo-position", help="Supply bench coordinates for five minutes")
    pos.add_argument("--lat", required=True, type=float)
    pos.add_argument("--lon", required=True, type=float)
    commands.add_parser("airdrop", help="Request 0.1 test SOL from the devnet faucet")
    send = commands.add_parser("report", help="Publish a road hazard (location is public)")
    send.add_argument("kind", choices=KINDS)
    send.add_argument("--lat", required=True, type=float)
    send.add_argument("--lon", required=True, type=float)
    send.add_argument("--ttl", type=int, default=900, help="Expiry in seconds, 60..3600")
    send.add_argument("--demo", action="store_true", help="Mark simulated coordinates/report")
    resolve = commands.add_parser("clear", help="Publish your observation that a report cleared")
    resolve.add_argument("report_id")
    read = commands.add_parser("nearby", help="Read verified reports from trusted riders")
    read.add_argument("--lat", required=True, type=float)
    read.add_argument("--lon", required=True, type=float)
    read.add_argument("--radius", type=float, default=1000)
    read.add_argument("--rider", action="append", help="Trusted rider public key; repeatable")
    read.add_argument("--include-demo", action="store_true")
    read.add_argument("--json", action="store_true")
    check = commands.add_parser("confirm", help="Check a previously submitted transaction")
    check.add_argument("signature")
    args = parser.parse_args()
    try:
        if args.command == "demo-position":
            from .network import coordinates

            lat, lon = coordinates(args.lat, args.lon)
            POSITION.parent.mkdir(parents=True, exist_ok=True)
            POSITION.write_text(
                json.dumps({"lat": lat, "lon": lon, "demo": True, "recorded_at": time.time()})
            )
            print("Demo position set for five minutes. Reports will be marked DEMO.")
            return
        if args.command == "init":
            key = wallet(args.wallet, create=True)
            print(f"Devnet rider: {key.pubkey()}")
            return
        with Network(args.rpc) as network:
            if args.command == "confirm":
                print("Confirmed" if network.confirm(args.signature) else "Not confirmed yet")
            elif args.command == "nearby":
                riders = args.rider or [
                    r for r in os.getenv("HELMETD_TRUSTED_RIDERS", "").split(",") if r
                ]
                if not riders and args.wallet.exists():
                    riders = [str(wallet(args.wallet).pubkey())]
                results = nearby(
                    network.events(riders), args.lat, args.lon, args.radius, args.include_demo
                )
                if args.json:
                    print(json.dumps(results, indent=2))
                elif not results:
                    print("No active reports found in the scanned trusted-rider feed.")
                else:
                    for item in results:
                        label = "DEMO " if item["demo"] else ""
                        print(
                            f"{label}{item['kind'].replace('_', ' ')} reported "
                            f"about {item['distance_m']} m away; "
                            f"expires in {max(0, item['expires_at'] - int(time.time()))} s"
                        )
                        print(f"  ID: {item['id']} | {explorer(item['signature'])}")
            else:
                key = wallet(args.wallet)
                if args.command == "airdrop":
                    signature = network.rpc("requestAirdrop", [str(key.pubkey()), 100000000])
                    print(explorer(signature), flush=True)
                    print("Confirmed" if network.confirm(signature) else "Airdrop pending")
                else:
                    data = (
                        report(args.kind, args.lat, args.lon, args.ttl, args.demo)
                        if args.command == "report"
                        else clear(args.report_id)
                    )
                    signature = network.publish(key, data)
                    print(f"Confirmed {data['op']}: {data['id']}")
                    print(explorer(signature))
    except (ValueError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")
    except FileNotFoundError:
        parser.exit(1, "Create the devnet wallet with helmetd-hazards init first.\n")
    except httpx.HTTPStatusError as error:
        parser.exit(
            1,
            f"Solana RPC returned HTTP {error.response.status_code}. "
            "For a rate-limited airdrop, use https://faucet.solana.com.\n",
        )
    except httpx.HTTPError:
        parser.exit(1, "Solana RPC could not be reached; no local detection is affected.\n")
    except KeyboardInterrupt:
        parser.exit(130, "Stopped. Check any printed transaction before resubmitting.\n")
