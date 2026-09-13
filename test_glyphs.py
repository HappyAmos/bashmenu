import bashmenu

def run_tests():
    # We'll mock the config and check interpolate_placeholders behavior
    config_nf_true = {
        "settings": {
            "use_nerd_fonts": True
        }
    }
    config_nf_false = {
        "settings": {
            "use_nerd_fonts": False
        }
    }

    # Test cases: (input_string, config, expected_output)
    test_cases = [
        # 1. 2-part format with emoji, NF=True: should show emoji (as we are in a unicode capable terminal)
        ("{nf:#f118:🚀}", config_nf_true, "🚀"),
        # 2. 2-part format with emoji, NF=False: should show the emoji
        ("{nf:#f118:🚀}", config_nf_false, "🚀"),
        
        # 3. 2-part format without emoji (empty emoji), NF=True: should show resolved nerd icon
        ("{nf:#f118:}", config_nf_true, ""),
        # 4. 2-part format without emoji (empty emoji), NF=False: should show nothing (no plain fallback defined)
        ("{nf:#f118:}", config_nf_false, ""),
        
        # 5. 3-part format with emoji, NF=True: should show the emoji
        ("{nf:>:#f118:👉}", config_nf_true, "👉"),
        # 6. 3-part format with emoji, NF=False: should show the emoji
        ("{nf:>:#f118:👉}", config_nf_false, "👉"),
        
        # 7. 3-part format without emoji, NF=True: should show resolved nerd icon
        ("{nf:>:#f118:}", config_nf_true, ""),
        # 8. 3-part format without emoji, NF=False: should show the plain text character
        ("{nf:>:#f118:}", config_nf_false, ">"),
    ]

    failed = 0
    for idx, (inp, conf, expected) in enumerate(test_cases):
        res = bashmenu.interpolate_placeholders(inp, conf)
        if res == expected:
            print(f"Test {idx+1} PASSED: {repr(inp)} -> {repr(res)}")
        else:
            print(f"Test {idx+1} FAILED: {repr(inp)} -> Expected {repr(expected)}, got {repr(res)}")
            failed += 1

    if failed == 0:
        print("All glyph tests passed!")
    else:
        print(f"{failed} tests failed.")
        assert False, f"{failed} tests failed."

if __name__ == "__main__":
    run_tests()
