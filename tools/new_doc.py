"""
Creates a documentation page.

Usage:
python tools/new_doc.py Position_Manager
"""

import sys

if len(sys.argv) != 2:
    print("Usage: python tools/new_doc.py Name")
    sys.exit(1)

name = sys.argv[1]

filename = f"docs/{name}.md"

with open(filename, "w") as f:
    f.write(f"# {name}\n\n")

print("Created", filename)
