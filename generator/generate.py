"""Entry point: python generator/generate.py [--out DIR] [--verify]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kestrel.build import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
