"""Package entry point: python -m marta"""

import os
import sys

# Transitional (stage 1): the legacy modules import each other flat
# ("import Buttons"), so running as a package needs the package directory
# itself on sys.path. Removed in stage 2 with the package-relative imports.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Marta import main

main()
