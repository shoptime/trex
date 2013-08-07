# coding: utf-8

# TODO - this only exists enough to indicate that two test files can exist, it really needs completing

from __future__ import absolute_import

from attest import Tests, Assert
from trex.support import tjson, quantum

tests = Tests()

@tests.test
def encoding():
    Assert(tjson.dumps({})) == '{}'
    Assert(tjson.dumps([])) == '[]'
    Assert(tjson.dumps('Hello')) == '"Hello"'

    with Assert.raises(quantum.QuantumException):
        Assert(tjson.dumps(quantum.now()))
