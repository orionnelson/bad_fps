"""Very small helper to author server map JSON.

This is a placeholder pipeline script to keep the repo aligned with the spec.
For real production, you'd export from Blender and enrich with pickups/spawns.

Input (example):
  python tools/export_map.py --out server/game/maps/map01.json
"""

from __future__ import annotations

import argparse
import json
import os


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # Minimal template.
    data = {
        "mapId": "map01",
        "bounds": {"center": [0.0, 1.5, 0.0], "size": [60.0, 6.0, 60.0]},
        "colliders": [],
        "spawns": [],
        "pickups": [],
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
