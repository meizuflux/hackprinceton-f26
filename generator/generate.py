# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "numpy==2.5.4",
#   "pillow==13.0.0",
#   "piexif==1.1.3",
#   "imageio-ffmpeg==0.8.1",
# ]
# ///
"""Entry point: uv run generator/generate.py [--out DIR] [--verify]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kestrel.build import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
