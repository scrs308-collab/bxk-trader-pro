"""
Creates a new BXK engine module.

Usage:
    python tools/new_engine.py MarketIntelligence
"""

import os
import sys

if len(sys.argv) != 2:
    print("Usage: python tools/new_engine.py EngineName")
    sys.exit(1)

name = sys.argv[1]

snake = ""

for i, c in enumerate(name):
    if c.isupper() and i > 0:
        snake += "_"
    snake += c.lower()

filename = f"bxk_app/{snake}.py"

template = f'''"""
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

'''

os.makedirs("bxk_app", exist_ok=True)

with open(filename, "w", encoding="utf-8") as f:
    f.write(template)

print(f"Created {{filename}}")
