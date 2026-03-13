#!/usr/bin/env python3
"""Build this ZMK user config locally inside the official build container."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path("/repo")
WORKSPACE = Path("/workspace")
OUTPUT_DIR = Path("/out")
CONFIG_SOURCE = REPO_ROOT / "config"
CONFIG_DEST = WORKSPACE / "config"
BUILD_MATRIX = REPO_ROOT / "build.yaml"
EXTRA_MODULES = REPO_ROOT


def run(*args: str) -> None:
    """Run a command and fail fast if it exits non-zero."""

    print("+", " ".join(shlex.quote(arg) for arg in args), flush=True)
    subprocess.run(args, check=True)


def sync_tree(source: Path, destination: Path) -> None:
    """Mirror the config tree into the cached workspace."""

    destination.mkdir(parents=True, exist_ok=True)

    source_entries = {path.relative_to(source) for path in source.rglob("*")}
    destination_entries = {
        path.relative_to(destination) for path in destination.rglob("*")
    }

    for relative_path in sorted(destination_entries - source_entries, reverse=True):
        path = destination / relative_path
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

    for source_path in sorted(source_entries):
        src = source / source_path
        dst = destination / source_path
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def load_build_matrix(path: Path) -> list[dict[str, str]]:
    """Load supported build entries from the standard ZMK build matrix file."""

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    entries: list[dict[str, str]] = []

    boards = data.get("board") or []
    shields = data.get("shield") or []
    if boards:
        if shields:
            for board in boards:
                for shield in shields:
                    entries.append({"board": board, "shield": shield})
        else:
            for board in boards:
                entries.append({"board": board})

    for item in data.get("include") or []:
        entries.append(item)

    if not entries:
        raise SystemExit(f"no build targets found in {path}")

    for item in entries:
        if "board" not in item:
            raise SystemExit(f"build target missing board: {item!r}")

    return entries


def artifact_stem(entry: dict[str, str]) -> str:
    """Match ZMK's default artifact naming for user config builds."""

    if entry.get("artifact-name"):
        return entry["artifact-name"]

    board = entry["board"].replace("/", "_")
    shield = entry.get("shield")
    if shield:
        return f"{shield}-{board}-zmk"

    return f"{board}-zmk"


def filter_targets(
    entries: list[dict[str, str]], filters: list[str]
) -> list[dict[str, str]]:
    """Optionally narrow the build list by artifact name, shield, or board."""

    if not filters:
        return entries

    lowered_filters = {item.casefold() for item in filters}
    filtered: list[dict[str, str]] = []

    for entry in entries:
        candidates = {
            artifact_stem(entry).casefold(),
            entry["board"].casefold(),
        }

        if entry.get("shield"):
            candidates.add(entry["shield"].casefold())

        if candidates & lowered_filters:
            filtered.append(entry)

    if filtered:
        return filtered

    raise SystemExit(f"no build targets matched filters: {', '.join(filters)}")


def ensure_workspace() -> None:
    """Initialize or refresh the cached west workspace."""

    sync_tree(CONFIG_SOURCE, CONFIG_DEST)

    if not (WORKSPACE / ".west").exists():
        run("west", "init", "-l", str(CONFIG_DEST))

    run("west", "update", "--fetch-opt=--filter=tree:0")
    run("west", "zephyr-export")


def build_target(entry: dict[str, str]) -> None:
    """Build one matrix entry and export its firmware artifact."""

    stem = artifact_stem(entry)
    build_dir = WORKSPACE / "build" / stem

    command = [
        "west",
        "build",
        "-p",
        "always",
        "-s",
        "zmk/app",
        "-d",
        str(build_dir),
        "-b",
        entry["board"],
    ]

    if entry.get("snippet"):
        command.extend(["-S", entry["snippet"]])

    command.append("--")
    command.append(f"-DZMK_CONFIG={CONFIG_DEST}")

    if entry.get("shield"):
        command.append(f"-DSHIELD={entry['shield']}")

    command.append(f"-DZMK_EXTRA_MODULES={EXTRA_MODULES}")

    if entry.get("cmake-args"):
        command.extend(shlex.split(entry["cmake-args"]))

    run(*command)

    uf2 = build_dir / "zephyr" / "zmk.uf2"
    bin_file = build_dir / "zephyr" / "zmk.bin"

    if uf2.exists():
        destination = OUTPUT_DIR / f"{stem}.uf2"
        shutil.copy2(uf2, destination)
        print(f"Wrote {destination}")
        return

    if bin_file.exists():
        destination = OUTPUT_DIR / f"{stem}.bin"
        shutil.copy2(bin_file, destination)
        print(f"Wrote {destination}")
        return

    raise SystemExit(f"no firmware artifact found for {stem}")


def main() -> int:
    """Build every target from build.yaml into ./build."""

    os.chdir(WORKSPACE)
    ensure_workspace()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = filter_targets(load_build_matrix(BUILD_MATRIX), sys.argv[1:])
    for entry in entries:
        build_target(entry)

    return 0


if __name__ == "__main__":
    sys.exit(main())
