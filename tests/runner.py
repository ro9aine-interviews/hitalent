import sys

import pytest


def main() -> int:
    return pytest.main(["-s", "tests"])


if __name__ == "__main__":
    sys.exit(main())
