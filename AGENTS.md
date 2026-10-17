# BashMenu Development Invariants & Guidelines

## 1. Mandatory Git Commit & Push Workflow
- **Commit & Push Requirement:** Every completed task, bug fix, feature, or refactoring step must conclude by creating a concise, descriptive git commit (`git commit -m "..."`) and pushing directly to GitHub (`git push origin main`).
- **Clean Workspace:** Never leave modified or newly created source/config files uncommitted or unpushed in the local repository.
- **Remote CI Verification:** After pushing to GitHub, verify remote CI passes using the GitHub CLI:
  - Query run ID: `gh run list --workflow=python-app.yml --limit 1`
  - Watch run: `gh run watch <ID>` (always pass an explicit ID to avoid interactive hangs).

## 2. Configuration & State Persistence
- **Config Header Preservation:** When saving or modifying `bashmenu.yml`, ALWAYS use `bashmenu.save_config(config)` instead of raw `yaml.dump()`. This guarantees the top-level `CONFIG_HEADER` is preserved.
- **Theme Editor Save Invariant:** <kbd>Ctrl+S</kbd> must save directly to disk whenever `theme_name` is set. Only untitled themes divert to "Save As". <kbd>Ctrl+A</kbd> opens "Save As".

## 3. Testing & Verification
- Always execute tests in `.tests/` before committing.
- In terminal scripts, do not assume `/usr/local/bin` for non-root users; install user CLI tools to `$HOME/.local/bin`.
