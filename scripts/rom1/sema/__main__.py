"""`python3 -m rom1.sema <view> ...` - the same dispatch `rom1 sema` uses."""

from __future__ import annotations

import sys

from rom1.sema import main

if __name__ == "__main__":
    sys.exit(main())
