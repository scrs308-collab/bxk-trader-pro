"""
Creates a new BXK engine module.

Usage:
    python tools/new_engine.py MarketIntelligenceEngine
"""

import os
import re
import sys

if len(sys.argv) != 2:
    print("Usage: python tools/new_engine.py EngineName")
    sys.exit(1)


def to_snake(name):
    """
    Converts:
        BXKCore -> bxk_core
        MarketDNAEngine -> market_dna_engine
        SPXScanner -> spx_scanner
        APIClient -> api_client
        OAuthManager -> oauth_manager
    """

    words = re.findall(
        r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|\d+",
        name
    )

    return "_".join(word.lower() for word in words)


name = sys.argv[1]
snake = to_snake(name)

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

print(f"Created {filename}")