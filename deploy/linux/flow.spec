Name:           flow
Version:        0.1.0
Release:        1%{?dist}
Summary:        Slide Presentation for Worship
License:        MIT
URL:            https://flow.example
Source0:        flow-%{version}.tar.gz

# Disable automatic dependency generation to avoid conflicts with 
# PyInstaller's hashed library names (e.g., libjpeg-xxxx.so)
AutoReqProv:    no
Requires:       python3, libX11, libXext, libXrender, libpng, libjpeg, libtiff, xz-libs

%description
Flow provides a professional and intuitive UI for worship slide presentation.
It supports PDF, PPTX, and image-based scores.

%install
mkdir -p %{buildroot}/usr/bin
mkdir -p %{buildroot}/usr/share/flow
mkdir -p %{buildroot}/usr/share/applications
mkdir -p %{buildroot}/usr/share/icons/hicolor/512x512/apps

# Copy files
cp -r %{_projectdir}/dist/Flow/* %{buildroot}/usr/share/flow/
cp %{_projectdir}/assets/splash.png %{buildroot}/usr/share/icons/hicolor/512x512/apps/flow.png

# Wrapper script
cat <<EOF > %{buildroot}/usr/bin/flow
#!/bin/bash
export PYTHONPATH="/usr/share/flow:\$PYTHONPATH"
cd "/usr/share/flow"
exec "/usr/share/flow/Flow" "\$@"
EOF
chmod +x %{buildroot}/usr/bin/flow

# Desktop file
cat <<EOF > %{buildroot}/usr/share/applications/flow.desktop
[Desktop Entry]
Type=Application
Name=Flow
Exec=flow
Icon=flow
Categories=Office;Presentation;
EOF

%files
/usr/bin/flow
/usr/share/flow/
/usr/share/applications/flow.desktop
/usr/share/icons/hicolor/512x512/apps/flow.png

%changelog
* Wed Jan 21 2026 Flow Team <contact@flow.example> - 0.1.0-1
- Initial release
