"""`python3 -m rom1.ghidra <verb> ...` - the same dispatch `rom1 ghidra` uses."""

from __future__ import annotations

import sys

from rom1.ghidra import main

if __name__ == "__main__":
    sys.exit(main())
