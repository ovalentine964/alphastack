#!/usr/bin/env bash
set -euo pipefail

# AlphaStack Mobile - Android Build Script
# Usage: ./build_android.sh [debug|release]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

BUILD_TYPE="${1:-debug}"

echo "╔══════════════════════════════════════╗"
echo "║   AlphaStack Mobile - Android Build   ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Pre-flight checks
echo "→ Checking Flutter installation..."
if ! command -v flutter &>/dev/null; then
    echo "✗ Flutter is not installed or not in PATH."
    echo "  Install from: https://docs.flutter.dev/get-started/install"
    exit 1
fi

FLUTTER_VERSION=$(flutter --version 2>/dev/null | head -1)
echo "  ✓ $FLUTTER_VERSION"

echo ""
echo "→ Checking Flutter doctor..."
flutter doctor --android-licenses 2>/dev/null || true

echo ""
echo "→ Getting dependencies..."
flutter pub get

echo ""
echo "→ Running code generation (json_serializable)..."
dart run build_runner build --delete-conflicting-outputs || echo "  ⚠ build_runner skipped (may already be up to date)"

echo ""
echo "→ Analyzing code..."
flutter analyze --no-fatal-infos || echo "  ⚠ Analysis completed with warnings"

echo ""
if [ "$BUILD_TYPE" = "release" ]; then
    echo "→ Building Android RELEASE APK..."
    flutter build apk --release
    echo ""
    echo "✓ Release APK built successfully!"
    echo "  Location: build/app/outputs/flutter-apk/app-release.apk"
else
    echo "→ Building Android DEBUG APK..."
    flutter build apk --debug
    echo ""
    echo "✓ Debug APK built successfully!"
    echo "  Location: build/app/outputs/flutter-apk/app-debug.apk"
fi

echo ""
echo "Done! 🚀"
