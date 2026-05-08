"""Allow ``python -m nus_client``."""

import sys

from nus_client.cli import main

sys.exit(main())
