#!/usr/bin/env python3
"""Demos for advanced composition of funktools decorators.
"""

import funktools


# Run with any of the following:
# - python3 -m demo.advanced entrypoint
# - python3 -m demo advanced entrypoint
@funktools.CLI()
def entrypoint() -> None:
    print('haha')


# Run with any of the following:
# - python3 -m demo advanced burst [arg]...
# - python3 -m demo.advanced burst [arg]...
#
# A few cool things to try:
# - python3 -m demo advanced burst
@funktools.CLI()
def burst(foo: int) -> None:
    ...


# Enables this CLI to be run with `python3 -m demo.advanced`.
if __name__ == '__main__':
    funktools.CLI(__name__).run()
