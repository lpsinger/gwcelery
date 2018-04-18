import os

import pytest

from ..util import NamedTemporaryFile


def test_named_temporary_file(tmpdir):
    """Test NamedTemporaryFile wrapper."""
    content = u'Hello world'
    with NamedTemporaryFile(prefix=str(tmpdir), content=content) as tmpfile:
        filename = tmpfile.name
        assert tmpfile.read() == content
    assert not os.path.exists(filename)


def test_named_temporary_file_unknown_type(tmpdir):
    """Test NamedTemporaryFile wrapper with content of the wrong type."""
    content = 12345
    with pytest.raises(TypeError):
        with NamedTemporaryFile(prefix=str(tmpdir), content=content):
            pass
