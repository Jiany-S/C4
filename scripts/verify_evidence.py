"""Verify original experiment artifacts on Windows, Linux, or an extracted ZIP."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]


def verify_manifest(folder):
    folder = Path(folder).resolve()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    checked = 0
    for relative, expected in manifest["sha256"].items():
        # The first Windows runs recorded backslashes. Preserve their bytes and hashes.
        path = (folder / relative.replace("\\", "/")).resolve()
        if not path.is_relative_to(folder):
            raise ValueError("Manifest path leaves its evidence directory.")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Evidence hash mismatch: {relative}")
        checked += 1
    return checked


def main():
    folders = [Path(p) for p in sys.argv[1:]] or [
        ROOT / "evidence/experiments_initial", ROOT / "evidence/experiments",
        ROOT / "evidence/new_scenarios"]
    for folder in folders:
        count = verify_manifest(folder)
        print(f"PASS: {folder.name}, {count} original JSON artifacts unchanged")


if __name__ == "__main__":
    main()
