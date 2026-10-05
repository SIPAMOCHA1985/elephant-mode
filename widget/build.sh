#!/bin/bash
# Build the universal (Apple Silicon + Intel) gauge binary into widget/bin/Gauge.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build bin
for arch in arm64 x86_64; do
  swiftc -O -target "$arch-apple-macos13" Gauge.swift -o "build/Gauge-$arch"
done
lipo -create build/Gauge-arm64 build/Gauge-x86_64 -output bin/Gauge
codesign --force --sign - bin/Gauge  # ad-hoc signature, required to run on Apple Silicon
lipo -info bin/Gauge
