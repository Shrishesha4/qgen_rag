#!/bin/zsh
set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
ANDROID_DIR="$PROJECT_ROOT/android"
APK_OUTPUT="$ANDROID_DIR/app/build/outputs/apk/release/app-release.apk"
FINAL_APK="$PROJECT_ROOT/client.apk"

export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export JAVA_HOME="${JAVA_HOME:-$(/usr/libexec/java_home -v 21 2>/dev/null || echo "/opt/homebrew/opt/openjdk@21")}"

# ─── Helpers ─────────────────────────────────────────────────────
bold()  { printf "\033[1m%s\033[0m\n" "$1"; }
green() { printf "\033[1;32m%s\033[0m\n" "$1"; }
red()   { printf "\033[1;31m%s\033[0m\n" "$1"; }

step() {
  bold "[$1/4] $2"
}

# ─── Pre-flight checks ──────────────────────────────────────────
command -v node >/dev/null 2>&1  || { red "Error: node not found."; exit 1; }
command -v npx >/dev/null 2>&1   || { red "Error: npx not found."; exit 1; }
command -v java >/dev/null 2>&1  || { red "Error: java not found."; exit 1; }
[[ -d "$ANDROID_HOME" ]] || { red "Error: Android SDK not found at $ANDROID_HOME"; exit 1; }
command -v "$ANDROID_HOME/tools/bin/sdkmanager" >/dev/null 2>&1 || { red "Error: Android SDK tools not properly installed."; exit 1; }

# ─── Step 1: Install JS dependencies & generate native dirs ────
step 1 "Preparing build environment..."
cd "$PROJECT_ROOT"
npm install --silent

# Generate native directories if missing
if [[ ! -d "$ANDROID_DIR" ]]; then
  bold "[native] Generating android/ via expo prebuild..."
  npx expo prebuild --clean --platform android
fi

# ─── Sync environment variables ─────────────────────────────────
bold "[env] Syncing environment variables..."
node scripts/sync-env.js

# Warn if PRODUCTION_API_URL is not set
PROD_URL=$(grep ^EXPO_PUBLIC_PRODUCTION_API_URL "$PROJECT_ROOT/.env.local" 2>/dev/null | cut -d= -f2)
if [[ -z "$PROD_URL" ]]; then
  red "Warning: EXPO_PUBLIC_PRODUCTION_API_URL is empty in client/.env.local."
  red "  The release APK will use the fallback URL baked into config/env.ts."
  red "  Set PRODUCTION_API_URL in the root .env.local if you want a different URL."
fi

# ─── Step 2: Clean old build ────────────────────────────────────
step 2 "Cleaning previous build..."
cd "$ANDROID_DIR"
./gradlew clean -q

# ─── Step 3: Build release APK ──────────────────────────────────
step 3 "Building release APK (this may take several minutes)..."
./gradlew assembleRelease -q

# ─── Step 4: Copy APK to project root ───────────────────────────
step 4 "Copying APK..."
if [[ -f "$APK_OUTPUT" ]]; then
  cp "$APK_OUTPUT" "$FINAL_APK"
  SIZE=$(du -h "$FINAL_APK" | cut -f1)
  green "Build successful! APK: $FINAL_APK ($SIZE)"
  echo ""
  echo "To install on your Android device:"
  echo "  Option A: adb install $FINAL_APK"
  echo "  Option B: Transfer the file to your phone and open it"
else
  red "Build failed — no APK produced."
  exit 1
fi
