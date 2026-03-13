#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
image="${ZMK_BUILD_IMAGE:-zmkfirmware/zmk-build-arm:stable}"
workspace_dir="${ZMK_WORKSPACE_DIR:-$repo_root/.build-cache/workspace}"
output_dir="${ZMK_OUTPUT_DIR:-$repo_root/build}"
home_dir="${ZMK_HOME_DIR:-$repo_root/.build-cache/home}"

if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required" >&2
    exit 1
fi

mkdir -p "$workspace_dir" "$output_dir" "$home_dir"

docker run --rm \
    --user "$(id -u):$(id -g)" \
    -e HOME=/home/build \
    -v "$repo_root:/repo" \
    -v "$workspace_dir:/workspace" \
    -v "$output_dir:/out" \
    -v "$home_dir:/home/build" \
    -w /repo \
    "$image" \
    python3 /repo/scripts/local_build.py "$@"
