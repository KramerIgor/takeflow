from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json


def main() -> int:
    parser = ArgumentParser(description="Merge one platform asset into the Takeflow update manifest.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--display-version", required=True)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--release-url", required=True)
    parser.add_argument("--asset-key", required=True)
    parser.add_argument("--asset-url", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--format", required=True)
    args = parser.parse_args()

    path = Path(args.manifest)
    manifest = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                manifest = loaded
        except (OSError, json.JSONDecodeError):
            manifest = {}

    manifest.update(
        {
            "version": args.version,
            "display_version": args.display_version,
            "release_tag": args.release_tag,
            "release_url": args.release_url,
        }
    )
    assets = manifest.get("assets")
    if not isinstance(assets, dict):
        assets = {}
    assets[args.asset_key] = {
        "url": args.asset_url,
        "sha256": args.sha256.lower(),
        "format": args.format,
    }
    manifest["assets"] = assets

    if args.asset_key == "windows-x64":
        manifest["installer_url"] = args.asset_url
        manifest["sha256"] = args.sha256.lower()

    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
