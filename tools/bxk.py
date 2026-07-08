"""
BXK Developer CLI

Usage:
    python tools/bxk.py version
    python tools/bxk.py status
    python tools/bxk.py doctor
    python tools/bxk.py new-engine MarketIntelligence
    python tools/bxk.py new-doc MarketIntelligence
    python tools/bxk.py release
    python tools/bxk.py backup
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run(command):
    return subprocess.run(
        command,
        shell=True,
        cwd=ROOT,
        capture_output=True,
        text=True
    )


def to_snake(name):
    output = ""
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            output += "_"
        output += char.lower()
    return output


def version():
    print("BXK Trader Pro")
    print("Production: V7.1.0")
    print("Development: V4")


def status():
    result = run("git status --short")
    branch = run("git branch --show-current").stdout.strip()

    print("BXK PROJECT STATUS")
    print("")
    print(f"Branch: {branch}")
    print("")

    if result.stdout.strip():
        print(result.stdout)
    else:
        print("Working tree clean")


def doctor():
    branch = run("git branch --show-current").stdout.strip()
    git_status = run("git status --short").stdout.strip()
    python_version = run("python --version").stdout.strip()

    print("BXK PROJECT HEALTH")
    print("")
    print(f"Branch................ {branch}")
    print(f"Python................ {python_version}")
    print(f"Git Clean............. {'YES' if not git_status else 'NO'}")
    print(f"Docs Folder........... {'YES' if (ROOT / 'docs').exists() else 'NO'}")
    print(f"App Folder............ {'YES' if (ROOT / 'bxk_app').exists() else 'NO'}")
    print(f"Static Folder......... {'YES' if (ROOT / 'static').exists() else 'NO'}")
    print("")
    print("Ready to develop" if not git_status else "Clean up Git changes first")


def new_engine(name):
    snake = to_snake(name)
    path = ROOT / "bxk_app" / f"{snake}.py"

    if path.exists():
        print(f"File already exists: {path}")
        return

    content = f'''"""
BXK Trader Pro

Module:
{name}

Version:
V4

Purpose:
TODO
"""


class {name}:
    def __init__(self):
        pass

    def evaluate(self):
        return {{}}
'''

    path.write_text(content, encoding="utf-8")
    print(f"Created {path}")


def new_doc(name):
    path = ROOT / "docs" / f"{name}.md"

    if path.exists():
        print(f"File already exists: {path}")
        return

    content = f"# {name}\n\n## Purpose\n\nTODO\n"
    path.write_text(content, encoding="utf-8")
    print(f"Created {path}")


def release():
    print("BXK RELEASE CHECKLIST")
    print("")
    print("[ ] Tests passing")
    print("[ ] Documentation updated")
    print("[ ] Git working tree clean")
    print("[ ] Version confirmed")
    print("[ ] Commit created")
    print("[ ] Push complete")
    print("[ ] Tag release")
    print("[ ] Deploy")


def backup():
    backup_dir = ROOT / "backups"
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    print(f"Backup folder ready: {backup_dir}")
    print(f"Suggested backup name: BXK_{timestamp}.zip")


def help_menu():
    print(__doc__)


COMMANDS = {
    "version": lambda args: version(),
    "status": lambda args: status(),
    "doctor": lambda args: doctor(),
    "new-engine": lambda args: new_engine(args[0]) if args else print("Missing engine name"),
    "new-doc": lambda args: new_doc(args[0]) if args else print("Missing doc name"),
    "release": lambda args: release(),
    "backup": lambda args: backup(),
    "help": lambda args: help_menu(),
}


def main():
    if len(sys.argv) < 2:
        help_menu()
        return

    command = sys.argv[1]
    args = sys.argv[2:]

    handler = COMMANDS.get(command)

    if not handler:
        print(f"Unknown command: {command}")
        help_menu()
        return

    handler(args)


if __name__ == "__main__":
    main()
