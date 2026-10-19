#!/bin/sh
# Credential-free self-test runner. Plain node (type stripping; no build
# step, no dependencies — the test path imports no host packages).
# Exits non-zero on any failure.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
node "$ROOT/pi/selftest/run.ts"
