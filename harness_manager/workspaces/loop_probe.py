"""Bounded filesystem probe for the desktop loop screen.

Project folders can live behind macOS privacy or network-volume gates. Keep
those reads out of the long-lived HTTP service so a blocked filesystem cannot
strand every refresh request.
"""
from __future__ import annotations

import hashlib
import json
import shlex
import sys
from pathlib import Path

from ..loops.runner import contract_digest
from ..loops.schema import load_contracts
from ..loops.storage import list_checkpoints


def filesystem_snapshot(root: Path) -> dict:
    contracts = []
    for path in sorted((root / ".agent/loops").glob("*.json")):
        if path.name in {"harnesses.json", "constraints.json", "budget.json"}:
            continue
        row = {
            "id": path.stem,
            "name": path.stem,
            "description": "",
            "digest": "",
            "autonomy": "",
            "executor": "",
            "checker": "",
            "limits": "",
            "capabilities": [],
            "error": "",
            "verification": "",
            "isolation": "",
        }
        try:
            data = load_contracts(root, path.stem)
            loop = data["loop"]
            maker = data["profiles"]["profiles"][loop["executor"]]
            row.update(
                description=loop["description"],
                digest=contract_digest(data),
                autonomy=loop["autonomy"],
                executor=loop["executor"],
                checker=loop.get("checker", ""),
                limits=json.dumps(
                    {key: min(value, data["budget"][key]) for key, value in loop["limits"].items()},
                    indent=2,
                ),
                capabilities=maker["capabilities"],
                isolation=loop["isolation"]["mode"],
                verification=shlex.join(loop.get("verification", {}).get("command", [])),
            )
        except (KeyError, TypeError, ValueError, OSError) as exc:
            row["error"] = str(exc)
        contracts.append(row)

    profiles = root / ".agent/loops/harnesses.json"
    digest = hashlib.sha256(profiles.read_bytes()).hexdigest() if profiles.is_file() else ""
    return {"contracts": contracts, "runs": list_checkpoints(root), "profileDigest": digest}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        return 2
    try:
        value = filesystem_snapshot(Path(args[0]))
        sys.stdout.write(json.dumps(value))
        return 0
    except (ValueError, OSError) as exc:
        sys.stderr.write(str(exc)[:1000])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
