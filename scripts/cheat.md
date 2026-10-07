# Cheat CLI

A lightweight CLI tool to search, list, and render Markdown cheatsheets.

## Features

- **Markdown Rendering**: Uses `rich.sh` (Python Rich) for terminal rendering with standard output fallback.
- **Tag Support**: Parses YAML frontmatter tags in cheatsheets.
- **Priority Search**: Matches filenames/paths first, then tags, then content.
- **Flexible Listing**: List all cheatsheets with tags or filter matches.

## Requirements

- Python 3.9+
- `PyYAML`
- `rich`

## Setup

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Update paths in `cheat.sh` to match your local installation directory.
3. Make `cheat.sh` executable and add it to your `PATH` or alias it:

```bash
chmod +x cheat.sh
```

## Configuration

The tool reads `.cheat.yml` located in the same directory as `cheat.py`.
It automatically creates a default config if one does not exist.

```yaml
dir: ~/cheat
```

`dir`: Path to the directory containing your Markdown cheatsheet files.

## Usage

### View a Cheatsheet

Find and display a cheatsheet by path, stem, tag, or text content:

```bash
cheat python/dicts
cheat docker
```

### List and Search Cheatsheets

List all available cheatsheets along with their frontmatter tags:

```bash
cheat -l
```

Filter listed files by path, tag, or text match:

```bash
cheat -l git
cheat -s git
```

### Print Configured Directory

Print the configured cheatsheets directory path:

```bash
cheat -d
# or
cheat --directory
```

You can also use this to quickly navigate to your cheatsheets directory in your shell:

```bash
cd "$(cheat -d)"
```

## Cheatsheet Format

Add YAML frontmatter tags to `.md` files to enable tag matching:

```markdown
---
tags: [git, vcs, undo]
---

# Git Undo Cheatsheet
...
```

## Search Resolution Order

1. Exact relative path or filename match
2. Frontmatter tag match
3. Full-text content search

