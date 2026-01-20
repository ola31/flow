#!/bin/bash

# Flow 리눅스 .rpm 패키지 빌드 자동화 스크립트
# ----------------------------------------
set -e

APP_NAME="Flow"
APP_LOWER="flow"
VERSION="0.1.0"
DIST_DIR="dist"

echo "📦 .rpm 패키지 빌드를 시작합니다..."

# 1. PyInstaller 빌드 확인
if [ ! -d "$DIST_DIR/$APP_NAME" ]; then
    echo "🔨 PyInstaller 빌드를 수행합니다..."
    pyinstaller Flow.spec --noconfirm
fi

# 2. rpmbuild 환경 확인
if ! command -v rpmbuild >/dev/null; then
    echo "❌ rpmbuild 명령어를 찾을 수 없습니다. (sudo dnf install rpm-build)"
    exit 1
fi

# 3. 빌드 수행 (rpmbuild --define 사용하여 현재 디렉토리 기준 빌드)
rpmbuild -bb --define "_topdir $(pwd)/rpm_build" \
         --define "_rpmdir $(pwd)/dist" \
         --define "_projectdir $(pwd)" \
         --define "buildroot $(pwd)/rpm_build/BUILDROOT" \
         deploy/linux/flow.spec

ARCH=$(arch)
echo "✅ .rpm 빌드 완료: dist/${ARCH}/${APP_LOWER}-${VERSION}-1.fc*.${ARCH}.rpm"
