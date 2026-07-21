#!/bin/sh
# electron-builder dmg target often fails on this Mac (dmgbuild/hdiutil attach).
# Build .app then wrap with hdiutil UDZO.
set -eu
cd "$(dirname "$0")/.."

npm run build
npx electron-builder --mac dir

APP="release/mac-arm64/MingoMate.app"
test -d "$APP"

STAGE="release/dmg-stage"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -sf /Applications "$STAGE/Applications"

VER=$(node -p "require('./package.json').version")
OUT="release/MingoMate-${VER}-arm64.dmg"
OUT2="release/vroid-base-custom-girl-${VER}-arm64.dmg"
rm -f "$OUT" "$OUT2"

hdiutil create \
  -volname "MingoMate ${VER}" \
  -srcfolder "$STAGE" \
  -ov -format UDZO \
  -imagekey zlib-level=9 \
  "$OUT"

cp -f "$OUT" "$OUT2"
ls -lh "$OUT" "$OUT2"
echo "OK: $OUT"
echo "OK: $OUT2"
