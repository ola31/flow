# Markdown Slide Format Smoke Test (manual)

**Setup:** Linux/Mac/Win — no PowerPoint or LibreOffice required.

## Steps

1. Open Flow, create a new project (or reuse one).
2. Add a new song. When prompted, choose **마크다운 (텍스트)**.
3. Editor opens with starter template. Verify:
   - ☐ Left pane shows markdown text (with syntax highlight: blue frontmatter, gold `# Title`, green `## section`)
   - ☐ Right pane shows preview + thumbnail strip below
4. Edit gradient: change title, add slides, add `> sub` overrides, add `{main_size: 80}` per-slide overrides.
5. Click **저장 (Ctrl+S)**. Verify:
   - ☐ File saved to disk
   - ☐ Preview re-renders to match
   - ☐ Tab dirty marker (if any) clears
6. Click **Frontmatter 편집**. Verify:
   - ☐ Form opens with current values
   - ☐ Change `main_size`, click OK
   - ☐ Frontmatter block updated, body preserved
7. Close editor. From the song list, click **편집** on the markdown song again. Verify:
   - ☐ Editor reopens with the saved content
8. Externally edit the `.md` file (with VS Code etc.). Save.
9. Verify in Flow:
   - ☐ Slide preview auto-updates
   - ☐ Live mode picks up the change

## Coexistence with PPT

10. In a song folder, place both `slides.md` and `slides.pptx`.
11. Verify Flow shows the markdown slides (not PPT).
12. Delete `slides.md`. Verify Flow falls back to PPT path.

## Failure modes

- Bad frontmatter (e.g. `main_size: "abc"`): edit triggers warning in console; defaults used; renderer doesn't crash.
- Missing background image (`background: "missing.jpg"`): falls back to black; warning logged.
- Empty `.md` file: 0 slides, no crash.
