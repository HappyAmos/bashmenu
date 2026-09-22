import os
import sys

# Mock curses BEFORE importing bashmenu
from unittest import mock

mock_curses = mock.MagicMock()
mock_curses.COLORS = 256
sys.modules['curses'] = mock_curses

# Set up paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bashmenu


class MockStdscr:
    def bkgd(self, *args): pass
    def erase(self): pass
    def refresh(self): pass

stdscr = MockStdscr()
config, _ = bashmenu.load_config()
theme = bashmenu.apply_theme(config.get("theme", "dracula"))
main_menu, _ = bashmenu.load_menu()
bashmenu.inject_dynamic_menus(main_menu)

def simulate(initial_selected_rows):
    print(f"\n--- Running simulation for initial path: {initial_selected_rows} ---")
    menu_stack = [main_menu]
    
    # Rebuild original menu stack
    curr_menu = main_menu
    for idx in initial_selected_rows[:-1]:
        selected_item = curr_menu.get("options", [])[idx]
        if "submenu" in selected_item:
            curr_menu = selected_item["submenu"]
            menu_stack.append(curr_menu)
            
    print(f"Before reload: menu_stack len = {len(menu_stack)}, selected_rows len = {len(initial_selected_rows)}")
    
    # Run original reload logic
    selected_rows = list(initial_selected_rows)
    _theme_new, _config_new = bashmenu.reload_environment(stdscr, menu_stack, selected_rows)
    
    print(f"After reload:  menu_stack len = {len(menu_stack)}, selected_rows len = {len(selected_rows)}")
    if len(menu_stack) != len(selected_rows):
        print("  WARNING: INVARIANT BROKEN!")
    else:
        print("  SUCCESS: Invariant holds.")

print("Original code behavior:")
simulate([1]) # Highlight "Applications" in root menu
simulate([1, 1]) # Highlight "Antigravity" inside "Applications"

# Now let's define the fixed reload_environment logic
def fixed_reload_environment(stdscr, menu_stack, selected_rows):
    config, _config_err = bashmenu.load_config()
    theme = bashmenu.apply_theme(config.get("theme", "dracula"))
    stdscr.bkgd(' ', theme["text"])

    main_menu, _menu_err = bashmenu.load_menu()
    bashmenu.inject_dynamic_menus(main_menu)

    saved_path = list(selected_rows)
    menu_stack.clear()
    selected_rows.clear()

    menu_stack.append(main_menu)
    curr_menu = main_menu

    for i, row_idx in enumerate(saved_path):
        opts = curr_menu.get("options", [])
        if not opts:
            selected_rows.append(0)
            break

        safe_idx = max(0, min(row_idx, len(opts) - 1))

        while safe_idx >= 0 and opts[safe_idx].get("type") == "divider":
            safe_idx -= 1
        if safe_idx < 0:
            safe_idx = 0
            while safe_idx < len(opts) and opts[safe_idx].get("type") == "divider":
                safe_idx += 1
            if safe_idx >= len(opts):
                safe_idx = 0

        selected_rows.append(safe_idx)

        # Only descend if there is a next level in the saved path
        if i < len(saved_path) - 1:
            selected_item = opts[safe_idx] if safe_idx < len(opts) else {}
            if "submenu" in selected_item:
                curr_menu = selected_item["submenu"]
                menu_stack.append(curr_menu)
            else:
                break

    if not selected_rows:
        selected_rows.append(0)

    return theme, config

# Patch and simulate again
bashmenu.reload_environment = fixed_reload_environment
print("\nFixed code behavior:")
simulate([1])
simulate([1, 1])
