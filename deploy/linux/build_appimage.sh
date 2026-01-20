#!/bin/bash

# Flow 리눅스 AppImage 빌드 자동화 스크립트
# ----------------------------------------
# 1. PyInstaller로 바이너리 생성
# 2. AppDir 구조 생성
# 3. appimagetool을 사용하여 .AppImage 생성

set -e

APP_NAME="Flow"
APP_LOWER="flow"
DIST_DIR="dist"
APPDIR="dist/AppDir"

echo "💎 AppImage 빌드를 시작합니다..."

# 1. PyInstaller 빌드 (이미 수행되지 않았다면)
if [ ! -d "$DIST_DIR/$APP_NAME" ]; then
    echo "🔨 PyInstaller 빌드를 수행합니다..."
    pyinstaller Flow.spec --noconfirm
fi

# 2. AppDir 구조 생성
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/icons/hicolor/512x512/apps"
mkdir -p "$APPDIR/usr/share/applications"

# 3. 바이너리 및 리소스 복사
cp -r "$DIST_DIR/$APP_NAME/." "$APPDIR/usr/bin/"
cp "assets/splash.png" "$APPDIR/usr/share/icons/hicolor/512x512/apps/$APP_LOWER.png"

# 4. AppRun 생성 (런처)
cat <<EOF > "$APPDIR/AppRun"
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\${0}")")"
export PYTHONPATH="\$HERE/usr/bin:\$PYTHONPATH"
exec "\$HERE/usr/bin/$APP_NAME" "\$@"
EOF
chmod +x "$APPDIR/AppRun"

# 5. 데스크탑 파일 복사/생성
cat <<EOF > "$APPDIR/$APP_LOWER.desktop"
[Desktop Entry]
Type=Application
Name=Flow
Exec=$APP_NAME
Icon=$APP_LOWER
Categories=Office;
EOF

# 6. appimagetool 실행 (시스템에 설치되어 있어야 함)
if command -v appimagetool >/dev/null; then
    VERSION=0.1.0 ARCH=x86_64 appimagetool "$APPDIR" "dist/$APP_NAME-x86_64.AppImage"
    echo "✅ AppImage 생성 완료: dist/$APP_NAME-x86_64.AppImage"
else
    echo "⚠️ appimagetool이 설치되어 있지 않습니다. dist/AppDir 구조만 생성되었습니다."
    echo "💡 https://github.com/AppImage/AppImageKit 에서 appimagetool을 다운로드하여 사용하세요."
fi
