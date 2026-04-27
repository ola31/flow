# LibreOffice Auto-Download Smoke Test (manual)

**Prerequisite:** Linux machine with NEITHER `soffice` in PATH NOR `/usr/bin/libreoffice`. To simulate, temporarily rename:

```bash
sudo mv /usr/bin/soffice /usr/bin/soffice.bak  # or whichever path exists
```

(Restore after the test: `sudo mv /usr/bin/soffice.bak /usr/bin/soffice`)

**Steps:**

1. Fill the manifest (one-time):
   ```bash
   python scripts/fill_libreoffice_manifest.py
   ```
2. Wipe any previous runtime:
   ```bash
   rm -rf ~/.local/share/Flow/runtime/libreoffice
   ```
3. Launch Flow and open a project containing a `.pptx`.
4. **Expect:** PreflightDialog appears with version + size + license note.
5. Click "지금 다운로드".
6. **Expect:** Progress dialog shows download → verify → extract phases. Total time ~1–3 min on broadband.
7. **Expect:** Dialog closes, slide preview populates.
8. Click the PPT edit button (in song list).
9. **Expect:** LibreOffice Impress GUI opens with the .pptx.
10. Restart Flow. Open the same .pptx.
11. **Expect:** No download dialog (runtime already installed).

**Failure modes to verify:**

- Cancel during download → dialog closes, `.download/` empty.
- Disconnect network mid-download → ErrorDialog with retry option.
- Manually corrupt INSTALLED_VERSION → next PPT load triggers re-download.
- Bump manifest version → next PPT load triggers upgrade dialog.
