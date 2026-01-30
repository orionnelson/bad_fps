"""Validate assets and generate a small manifest.

This keeps the repo layout clean while making it easy to deploy the client.

Usage:
  python tools/pack_assets.py

Effect:
  - copies shared/constants.json and shared/schema.json into client/public/shared/
  - writes client/public/assets/manifest.json
"""

from __future__ import annotations

import json
import os
import shutil


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main() -> int:
    root = _repo_root()
    shared_dir = os.path.join(root, "shared")
    client_public = os.path.join(root, "client", "public")

    out_shared = os.path.join(client_public, "shared")
    os.makedirs(out_shared, exist_ok=True)

    copied = []
    for name in ("constants.json", "schema.json"):
        src = os.path.join(shared_dir, name)
        dst = os.path.join(out_shared, name)
        if os.path.exists(src):
            shutil.copyfile(src, dst)
            copied.append({"src": f"shared/{name}", "dst": f"client/public/shared/{name}"})

    assets_dir = os.path.join(client_public, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    manifest_path = os.path.join(assets_dir, "manifest.json")
    manifest = {"copied": copied}
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
