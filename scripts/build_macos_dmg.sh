#!/usr/bin/env bash
set -euo pipefail

arch="${1:-$(uname -m)}"
case "$arch" in
  arm64) asset_arch="AppleSilicon" ;;
  x86_64) asset_arch="Intel" ;;
  *) echo "Unsupported macOS architecture: $arch" >&2; exit 2 ;;
esac

project_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_root"

app_version="$(python -c 'from app.version import APP_VERSION; print(APP_VERSION)')"
display_version="$(python -c 'from app.version import APP_VERSION_DISPLAY; print(APP_VERSION_DISPLAY)')"
dist_root="$project_root/dist/macos/$arch"
work_root="$project_root/build/macos-$arch"
stage_root="$work_root/dmg-root"
dmg_path="$project_root/dist/Takeflow-${app_version}-macOS-${asset_arch}.dmg"

echo "Building Takeflow $display_version for macOS $arch"
rm -rf "$dist_root" "$work_root"
mkdir -p "$dist_root" "$stage_root"

export TAKEFLOW_TARGET_ARCH="$arch"
python -m PyInstaller packaging/pyinstaller_takeflow_macos.spec \
  --noconfirm \
  --clean \
  --distpath "$dist_root" \
  --workpath "$work_root/pyinstaller"

app_path="$dist_root/Takeflow.app"
if [[ ! -d "$app_path" ]]; then
  echo "Takeflow.app was not produced at $app_path" >&2
  exit 1
fi

codesign --force --deep --sign - "$app_path"
codesign --verify --deep --strict "$app_path"

cp -R "$app_path" "$stage_root/Takeflow.app"
ln -s /Applications "$stage_root/Applications"
rm -f "$dmg_path"
hdiutil create \
  -volname "Takeflow" \
  -srcfolder "$stage_root" \
  -format UDZO \
  -ov \
  "$dmg_path"

shasum -a 256 "$dmg_path" | tee "$dmg_path.sha256"
echo "DMG_PATH=$dmg_path"
