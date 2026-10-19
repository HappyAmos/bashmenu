# BashMenu Development Invariants & Guidelines

## 1. Mandatory Git Commit & Push Workflow
- **Commit & Push Requirement:** Every completed task, bug fix, feature, or refactoring step must conclude by creating a concise, descriptive git commit (`git commit -m "..."`) and pushing directly to GitHub (`git push origin main`).
- **Clean Workspace:** Never leave modified or newly created source/config files uncommitted or unpushed in the local repository.
- **Remote CI Verification:** After pushing to GitHub, verify remote CI passes using the GitHub CLI:
  - Query run ID: `gh run list --workflow=python-app.yml --limit 1` (and `--workflow=shellcheck-app.yml`)
  - Watch run: `gh run watch <ID>` (always pass an explicit ID to avoid interactive hangs).

## 2. Configuration & State Persistence
- **Config Header Preservation:** When saving or modifying `bashmenu.yml`, ALWAYS use `bashmenu.save_config(config)` instead of raw `yaml.dump()`. This guarantees the top-level `CONFIG_HEADER` is preserved.
- **Theme Editor Save Invariant:** <kbd>Ctrl+S</kbd> must save directly to disk whenever `theme_name` is set. Only untitled themes divert to "Save As". <kbd>Ctrl+A</kbd> opens "Save As".

## 3. Testing & Verification
- Always execute tests in `.tests/` before committing.
- In terminal scripts, do not assume `/usr/local/bin` for non-root users; install user CLI tools to `$HOME/.local/bin`.

## 4. Textual UI Performance & Responsiveness Invariants
- **Avoid Stylesheet Invalidation Cascades:** Never call `remove_class()` / `add_class()` in hot interactive paths or collapsible accordions. In Textual, class mutations trigger `update_styles()` which re-evaluates all DOM nodes against CSS rules. Use direct property manipulation (`widget.display = True/False`) combined with direct class set tracking (`widget._classes.discard(...)` / `widget._classes.add(...)`).
- **Instant Scrolling & Zero-Delay Focus:** Always pass `animate=False` to `widget.scroll_visible()` when focusing or jumping to elements. Avoid `Widget.focus()` in latency-sensitive paths as it defers via `call_later` and defaults to animated `scroll_to_center`; use `self.set_focus(widget, scroll_visible=False)` with a post-refresh instant scroll instead.
- **Immediate Mouse Interaction:** Handle `events.MouseDown` directly rather than waiting for `events.Click` (which only fires after `MouseUp` and is suppressed if the cursor shifts slightly during click) so users get instantaneous feedback without perceptible lag.
- **Batched DOM Updates:** Wrap multi-widget updates, section expansions, and focus shifts in `with self.app.batch_update():` to coalesce layout reflows into a single frame.

