#!/usr/bin/env python

from atools import cli


@cli
def entrypoint(foo: int, /) -> dict[str, int]:
    return locals()
