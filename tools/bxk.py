"""
BXK Developer CLI

Usage:
    python tools/bxk.py version
    python tools/bxk.py status
    python tools/bxk.py doctor
    python tools/bxk.py start
    python tools/bxk.py new-engine MarketIntelligenceEngine
    python tools/bxk.py new-doc MarketIntelligence
    python tools/bxk.py release
    python tools/bxk.py backup
"""

import re
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_URL = "http://127.0.0.1:8000"


def run(command: str):
    return subprocess.run(
        command,
        shell=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def to_snake(name: str) -> str:
    words = re.findall(
        r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|\d+",
        name,
    )
    return "_".join(word.lower() for word in words)


def version():
    print("BXK Trader Pro")
    print("Production: V7.1.0")
    print("Development: V4")


def status():
    branch = run("git branch --show-current").stdout.strip()
    changes = run("git status --short").stdout.strip()

    print("\nBXK PROJECT STATUS\n")
    print(f"Branch: {branch}\n")

    if changes:
        print(changes)
    else:
        print("Working tree clean")


def doctor():
    branch = run("git branch --show-current").stdout.strip()
    changes = run("git status --short").stdout.strip()
    python_version = run("python --version").stdout.strip()

    print("\nBXK PROJECT HEALTH\n")
    print(f"Branch................ {branch}")
    print(f"Python................ {python_version or 'NOT FOUND'}")
    print(f"Git Clean............. {'YES' if not changes else 'NO'}")
    print(f"Docs Folder........... {'YES' if (ROOT / 'docs').exists() else 'NO'}")
    print(f"App Folder............ {'YES' if (ROOT / 'bxk_app').exists() else 'NO'}")
    print(f"Static Folder......... {'YES' if (ROOT / 'static').exists() else 'NO'}")
    print(f"Requirements.......... {'YES' if (ROOT / 'requirements.txt').exists() else 'NO'}")
    print(f"Server................ {'YES' if (ROOT / 'server.py').exists() else 'NO'}")
    print("\nReady to develop" if not changes else "\nClean up Git changes first")


def start():
    print("\nStarting BXK Trader Pro...\n")

    branch = run("git branch --show-current").stdout.strip()
    if branch != "v4":
        print(f"Current branch is '{branch}'. Switching to v4...")
        checkout = run("git checkout v4")
        if checkout.returncode != 0:
            print(checkout.stderr)
            print("Could not switch to v4. Start aborted.")
            return

    print("Pulling latest changes...")
    pull = run("git pull")
    if pull.stdout.strip():
        print(pull.stdout.strip())
    if pull.stderr.strip():
        print(pull.stderr.strip())

    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    python_cmd = str(venv_python) if venv_python.exists() else "python"

    print("\nLaunching server...")
    subprocess.Popen(
        [python_cmd, "server.py"],
        cwd=ROOT,
    )

    time.sleep(3)
    webbrowser.open(DASHBOARD_URL)

    print(f"\nDashboard opened: {DASHBOARD_URL}")
    print("Server running. Leave this terminal open.")


def new_engine(name: str):
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

    def run(self):
        return {{}}
'''

    path.write_text(content, encoding="utf-8")
    print(f"Created {path}")


def new_doc(name: str):
    path = ROOT / "docs" / f"{name}.md"

    if path.exists():
        print(f"File already exists: {path}")
        return

    content = f"# {name}\n\n## Purpose\n\nTODO\n"
    path.write_text(content, encoding="utf-8")
    print(f"Created {path}")


def release():
    print(
        """
BXK RELEASE CHECKLIST

[ ] Tests passing
[ ] Documentation updated
[ ] Git working tree clean
[ ] Version confirmed
[ ] Commit created
[ ] Push complete
[ ] Tag release
[ ] Deploy
"""
    )


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
    "start": lambda args: start(),
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