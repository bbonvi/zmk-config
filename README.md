Sofle\Soufflé ZMK firmware.

Local builds use Docker instead of GitHub Actions:

```bash
./build.sh
./build.sh sofle_right
```

Artifacts are written to `./build/`. The script keeps a reusable west
workspace in `./.build-cache/workspace/` so repeat builds stay fast. The
targets come from `build.yaml`; passing an argument limits the build to a
matching artifact name, shield, or board.
