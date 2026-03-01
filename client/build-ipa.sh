#!/bin/zsh
set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
IOS_DIR="$PROJECT_ROOT/ios"
WORKSPACE="$IOS_DIR/client.xcworkspace"
SCHEME="client"
ARCHIVE_PATH="$IOS_DIR/build/client.xcarchive"
EXPORT_OPTIONS="$IOS_DIR/ExportOptions.plist"
EXPORT_PATH="$IOS_DIR/build/ipa"
TEAM_ID="U7TNVB7U48"

# ─── Helpers ─────────────────────────────────────────────────────
bold()  { printf "\033[1m%s\033[0m\n" "$1"; }
green() { printf "\033[1;32m%s\033[0m\n" "$1"; }
red()   { printf "\033[1;31m%s\033[0m\n" "$1"; }

step() {
  bold "[$1/5] $2"
}

# ─── Pre-flight checks ──────────────────────────────────────────
command -v xcodebuild >/dev/null 2>&1 || { red "Error: xcodebuild not found. Install Xcode."; exit 1; }
command -v node >/dev/null 2>&1       || { red "Error: node not found."; exit 1; }
command -v npx >/dev/null 2>&1        || { red "Error: npx not found."; exit 1; }

# ─── Step 1: Install JS dependencies ────────────────────────────
step 1 "Installing JS dependencies..."
cd "$PROJECT_ROOT"
npm install --silent

# ─── Step 2: Clean old build artifacts ──────────────────────────
step 2 "Cleaning old build artifacts..."
rm -rf "$ARCHIVE_PATH" "$EXPORT_PATH"

# ─── Step 3: Install CocoaPods ───────────────────────────────────
step 3 "Installing CocoaPods dependencies..."
cd "$IOS_DIR"
rm -rf Pods Podfile.lock
pod install --silent

# ─── Step 4: Archive ────────────────────────────────────────────
step 4 "Archiving (this may take a few minutes)..."
xcodebuild \
  -workspace "$WORKSPACE" \
  -scheme "$SCHEME" \
  -sdk iphoneos \
  -configuration Release \
  -archivePath "$ARCHIVE_PATH" \
  archive \
  CODE_SIGN_IDENTITY="Apple Development" \
  DEVELOPMENT_TEAM="$TEAM_ID" \
  CODE_SIGN_STYLE=Automatic \
  -quiet

# ─── Step 5: Export .ipa ─────────────────────────────────────────
step 5 "Exporting .ipa..."
xcodebuild \
  -exportArchive \
  -archivePath "$ARCHIVE_PATH" \
  -exportOptionsPlist "$EXPORT_OPTIONS" \
  -exportPath "$EXPORT_PATH" \
  -quiet

# ─── Done ────────────────────────────────────────────────────────
IPA_FILE="$EXPORT_PATH/client.ipa"
if [[ -f "$IPA_FILE" ]]; then
  SIZE=$(du -h "$IPA_FILE" | cut -f1)
  green "Build successful! IPA: $IPA_FILE ($SIZE)"
  echo ""
  echo "To install on your iPhone:"
  echo "  1. Connect via USB"
  echo "  2. Drag the .ipa onto your device in Finder"
  echo "  3. Trust the profile in Settings > General > VPN & Device Management"
else
  red "Export failed — no .ipa produced."
  exit 1
fi
