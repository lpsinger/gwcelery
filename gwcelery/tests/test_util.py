import sys

import pytest

from .. import util


def test_handling_exit_0():
    with util.handling_system_exit():
        sys.exit(0)


def test_handling_exit_1():
    with pytest.raises(RuntimeError):
        with util.handling_system_exit():
            sys.exit(1)
