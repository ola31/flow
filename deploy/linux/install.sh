#!/bin/bash

# Flow 리눅스 통합 설치 스크립트
# 1. 앱 디렉토리 설정
# 2. 아이콘 및 .desktop 파일 생성/등록

set -e

APP_NAME="Flow"
APP_EXEC="flow"
INSTALL_DIR="$HOME/.local/share/flow"
BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"
DESKTOP_DIR="$HOME/.local/share/applications"

echo "📦 $APP_NAME 설치를 시작합니다..."

# 1. 디렉토리 생성
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$ICON_DIR"
mkdir -p "$DESKTOP_DIR"

# 2. 파일 복사 (현재 디렉토리의 소스를 설치 디렉토리로)
# 실제 AppImage나 빌드된 바이너리가 있는 경우 해당 파일을 복사하도록 수정 가능
# 지금은 소스 기반 실행을 지원하도록 구성
cp -r . "$INSTALL_DIR/"

# 3. 아이콘 설치
if [ -f "assets/splash.png" ]; then
    cp "assets/splash.png" "$ICON_DIR/flow.png"
fi

# 4. 실행 래퍼(Wrapper) 스크립트 생성
cat <<EOF > "$BIN_DIR/$APP_EXEC"
#!/bin/bash
export PYTHONPATH="$INSTALL_DIR/src:\$PYTHONPATH"
cd "$INSTALL_DIR"
python3 src/flow/main.py "\$@"
EOF
chmod +x "$BIN_DIR/$APP_EXEC"

# 5. 데스크탑 엔트리(.desktop) 생성
cat <<EOF > "$DESKTOP_DIR/flow.desktop"
[Desktop Entry]
Type=Application
Name=Flow
Comment=Slide Presentation for Worship
Exec=$BIN_DIR/$APP_EXEC
Icon=flow
Terminal=false
Categories=Office;Presentation;
EOF

chmod +x "$DESKTOP_DIR/flow.desktop"

echo "✅ 설치 완료!"
echo "🚀 이제 앱 메뉴(Launcher)에서 'Flow'를 검색하여 실행하시거나, 터미널에서 '$APP_EXEC'를 입력하세요."
echo "💡 (참고: '$BIN_DIR'이 PATH에 등록되어 있어야 터미널 명령어가 작동합니다.)"
