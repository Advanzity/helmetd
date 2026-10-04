"""Voice tools use a fresh local position, never coordinates guessed by the LLM."""

import json
import os
import time
from pathlib import Path

from .network import Network, coordinates, explorer, nearby, report, wallet

POSITION = Path(".local/hazards/position.json")


def position(path=POSITION, now=None):
    now = time.time() if now is None else now
    try:
        data = json.loads(path.read_text())
        if type(data.get("demo")) is not bool:
            raise ValueError
        if type(data.get("recorded_at")) not in (int, float):
            raise ValueError
        age = now - data["recorded_at"]
        if not 0 <= age <= (300 if data["demo"] else 10):
            raise ValueError
        coordinates(data["lat"], data["lon"])
        return data
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError(
            "No fresh location is available. Connect GPS or set a demo position."
        ) from None


def check_nearby(_):
    try:
        pos = position()
        riders = [
            r.strip() for r in os.getenv("HELMETD_TRUSTED_RIDERS", "").split(",") if r.strip()
        ]
        if not riders:
            riders = [str(wallet().pubkey())]
        with Network() as network:
            results = nearby(
                network.events(riders), pos["lat"], pos["lon"], include_demo=pos["demo"]
            )
        return json.dumps(
            {
                "status": "ok",
                "demo": pos["demo"],
                "reports": [
                    {
                        "kind": r["kind"],
                        "distance_m": r["distance_m"],
                        "clear_observations": r["clear_observations"],
                    }
                    for r in results[:3]
                ],
                "note": "Community reports only; no reports does not mean a safe road.",
            }
        )
    except ValueError as error:
        return json.dumps({"status": "unavailable", "reason": str(error)})
    except Exception:
        return json.dumps({"status": "unavailable", "reason": "Could not read the hazard network."})


def report_hazard(parameters):
    try:
        pos = position()
        data = report(parameters.get("kind"), pos["lat"], pos["lon"], demo=pos["demo"])
        with Network() as network:
            signature = network.publish(wallet(), data)
        return json.dumps(
            {
                "status": "confirmed",
                "demo": pos["demo"],
                "report_id": data["id"],
                "transaction": explorer(signature),
            }
        )
    except ValueError as error:
        return json.dumps({"status": "not_sent", "reason": str(error)})
    except Exception:
        return json.dumps(
            {
                "status": "unconfirmed",
                "reason": "Check the local transaction log. "
                "Do not claim success or retry automatically.",
            }
        )
