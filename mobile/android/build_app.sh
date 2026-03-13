#!/bin/bash
# Build script for AnimeCaos Mobile Android App
# Usage: ./build_app.sh [debug|release] [api_url]

set -e

cd "$(dirname "$0")"

BUILD_TYPE="${1:-debug}"
API_URL="${2:-http://10.0.0.4:8000/}"

echo "=============================================="
echo "AnimeCaos Mobile - Android Build"
echo "=============================================="
echo "Build type: $BUILD_TYPE"
echo "API URL: $API_URL"
echo "=============================================="

if [ "$BUILD_TYPE" = "release" ]; then
    echo "Building RELEASE APK..."
    ./gradlew assembleRelease -PapiBaseUrl="$API_URL"
    echo ""
    echo "✓ Release APK generated:"
    echo "  app/build/outputs/apk/release/app-release.apk"
else
    echo "Building DEBUG APK..."
    ./gradlew assembleDebug -PapiBaseUrl="$API_URL"
    echo ""
    echo "✓ Debug APK generated:"
    echo "  app/build/outputs/apk/debug/app-debug.apk"
fi

echo ""
echo "To install on device:"
echo "  adb install app/build/outputs/apk/${BUILD_TYPE}/app-${BUILD_TYPE}.apk"
