# coding: utf-8

from __future__ import absolute_import
from attest import Tests
from os import path
from glob import glob

__all__ = [m for m in [path.basename(f)[:-3] for f in glob(path.dirname(__file__) + '/*.py')] if m not in ['__init__']]
from . import *

tests = Tests()

for module in __all__:
    tests.register("trex.self_tests.%s.tests" % module)

