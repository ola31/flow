#!/bin/bash

# Flow 리눅스 .deb 패키지 빌드 자동화 스크립트
# ----------------------------------------
set -e

APP_NAME="Flow"
APP_LOWER="flow"
VERSION="0.1.0"
DEB_ROOT="dist/deb_root"
DIST_DIR="dist"

echo "📦 .deb 패키지 빌드를 시작합니다..."

# 1. PyInstaller 빌드 확인
if [ ! -d "$DIST_DIR/$APP_NAME" ]; then
    echo "🔨 PyInstaller 빌드를 수행합니다..."
    pyinstaller Flow.spec --noconfirm
fi

# 2. 구조 생성
rm -rf "$DEB_ROOT"
mkdir -p "$DEB_ROOT/DEBIAN"
mkdir -p "$DEB_ROOT/usr/bin"
mkdir -p "$DEB_ROOT/usr/share/flow"
mkdir -p "$DEB_ROOT/usr/share/applications"
mkdir -p "$DEB_ROOT/usr/share/icons/hicolor/512x512/apps"

# 3. 메타데이터 및 파일 복사
cp deploy/linux/DEBIAN/control "$DEB_ROOT/DEBIAN/"
cp -r "$DIST_DIR/$APP_NAME/." "$DEB_ROOT/usr/share/flow/"
cp "assets/splash.png" "$DEB_ROOT/usr/share/icons/hicolor/512x512/apps/$APP_LOWER.png"

# 4. 실행 래퍼(Wrapper) 스크립트 생성
cat <<EOF > "$DEB_ROOT/usr/bin/$APP_LOWER"
#!/bin/bash
export PYTHONPATH="/usr/share/flow:\$PYTHONPATH"
cd "/usr/share/flow"
exec "/usr/share/flow/$APP_NAME" "\$@"
EOF
chmod +x "$DEB_ROOT/usr/bin/$APP_LOWER"

# 5. 데스크탑 파일 생성
cat <<EOF > "$DEB_ROOT/usr/share/applications/$APP_LOWER.desktop"
[Desktop Entry]
Type=Application
Name=Flow
Exec=$APP_LOWER
Icon=$APP_LOWER
Categories=Office;Presentation;
EOF

# 6. 패키지 생성
dpkg-deb --build "$DEB_ROOT" "dist/${APP_LOWER}_${VERSION}_amd64.deb"

echo "✅ .deb 빌드 완료: dist/${APP_LOWER}_${VERSION}_amd64.deb"
