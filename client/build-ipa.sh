#!/bin/zsh
set -euo pipefail

# ─── Helpers ─────────────────────────────────────────────────────
bold()   { printf "\033[1m%s\033[0m\n" "$1"; }
green()  { printf "\033[1;32m%s\033[0m\n" "$1"; }
red()    { printf "\033[1;31m%s\033[0m\n" "$1"; }
yellow() { printf "\033[1;33m%s\033[0m\n" "$1"; }

step() {
  bold "[$1/5] $2"
}

# ─── Configuration ───────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
IOS_DIR="$PROJECT_ROOT/ios"
WORKSPACE="$IOS_DIR/QGen.xcworkspace"
SCHEME="QGen"
ARCHIVE_PATH="$IOS_DIR/build/QGen.xcarchive"
EXPORT_OPTIONS="$IOS_DIR/ExportOptions.plist"
EXPORT_PATH="$IOS_DIR/build/ipa"

# Development Team ID (optional for signing). Set via DEVELOPMENT_TEAM env var,
# or it will be auto-detected from the first available provisioning profile.
# If not found, xcodebuild will attempt auto-provisioning with -allowProvisioningUpdates.
DEVELOPMENT_TEAM="${DEVELOPMENT_TEAM:-}"
if [[ -z "$DEVELOPMENT_TEAM" ]]; then
  # Try to extract from provisioning profiles
  PP_PATH="$HOME/Library/MobileDevice/Provisioning\ Profiles"
  if [[ -d "$PP_PATH" ]]; then
    # Try to find the team ID from the first provisioning profile
    for file in "$PP_PATH"/*.mobileprovision; do
      if [[ -f "$file" ]]; then
        TEAM_ID=$(security cms -D -i "$file" 2>/dev/null | grep -o 'TeamIdentifier.*</key>' | head -1 | sed 's/.*<string>//;s/<\/string>.*//' 2>/dev/null || echo "")
        if [[ ! -z "$TEAM_ID" ]]; then
          DEVELOPMENT_TEAM="$TEAM_ID"
          bold "[team] Found DEVELOPMENT_TEAM in provisioning profiles: $DEVELOPMENT_TEAM"
          break
        fi
      fi
    done
  fi
fi

if [[ -z "$DEVELOPMENT_TEAM" ]]; then
  yellow "[team] No development team found. Will attempt auto-provisioning."
  yellow "  If this fails, set: export DEVELOPMENT_TEAM='XXXXX'"
else
  bold "[team] Using DEVELOPMENT_TEAM=$DEVELOPMENT_TEAM"
fi

# ─── Pre-flight checks ──────────────────────────────────────────
command -v xcodebuild >/dev/null 2>&1 || { red "Error: xcodebuild not found. Install Xcode."; exit 1; }
command -v node >/dev/null 2>&1       || { red "Error: node not found."; exit 1; }
command -v npx >/dev/null 2>&1        || { red "Error: npx not found."; exit 1; }

# ─── Step 1: Install JS dependencies & generate native dirs ────
step 1 "Preparing build environment..."
cd "$PROJECT_ROOT"
npm install --silent

# Always regenerate native directories to pick up latest app.json (name, icon, etc.)
bold "[native] Regenerating ios/ via expo prebuild..."
npx expo prebuild --clean --platform ios

# ─── Sync environment variables ─────────────────────────────────
bold "[env] Syncing environment variables..."
node scripts/sync-env.js

# Warn if PRODUCTION_API_URL is not set
PROD_URL=$(grep ^EXPO_PUBLIC_PRODUCTION_API_URL "$PROJECT_ROOT/.env.local" 2>/dev/null | cut -d= -f2)
if [[ -z "$PROD_URL" ]]; then
  red "Warning: EXPO_PUBLIC_PRODUCTION_API_URL is empty in client/.env.local."
  red "  The release IPA will use the fallback URL baked into config/env.ts."
fi

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

# Build xcodebuild command with conditional DEVELOPMENT_TEAM setting
TEAM_FLAG=""
if [[ ! -z "$DEVELOPMENT_TEAM" ]]; then
  TEAM_FLAG="DEVELOPMENT_TEAM=$DEVELOPMENT_TEAM"
fi

xcodebuild \
  -workspace "$WORKSPACE" \
  -scheme "$SCHEME" \
  -sdk iphoneos \
  -configuration Release \
  -archivePath "$ARCHIVE_PATH" \
  -allowProvisioningUpdates \
  archive \
  CODE_SIGN_STYLE=Automatic \
  $TEAM_FLAG \
  NODE_BINARY="$(command -v node)" \
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
IPA_FILE="$EXPORT_PATH/QGen.ipa"
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
