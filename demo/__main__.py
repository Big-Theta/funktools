#!/usr/bin/env python3
"""Demo for package-level main.

Ex.

```bash
python3 -m demo -h
```

"""

import logging

import funktools

from . import cli as _, throttle as _

logging.basicConfig(level=logging.CRITICAL, format='%(levelname)s: %(message)s')

funktools.CLI().run(__package__)
