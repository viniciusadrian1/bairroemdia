"""File envelopes cross a browser boundary; validate them independently."""
import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from frontend.ui.upload import decode_upload


def test_upload_preserves_exact_bytes_and_uses_actual_size():
    data = b"synthetic-image-bytes"
    result = decode_upload({"name": "foto.PNG", "base64": base64.b64encode(data).decode(), "size": 0}, ["png"], 100)
    assert result.getvalue() == data
    assert result.size == len(data)


@pytest.mark.parametrize("value", [
    "not an object", {"name": "image.exe", "base64": "YWJj"},
    {"name": "image.png", "base64": "not base64!"},
    {"name": "image.png", "base64": ""},
    {"name": "image.png", "base64": base64.b64encode(b"123456").decode(), "size": 1},
])
def test_upload_rejects_invalid_or_oversized_envelopes(value):
    with pytest.raises(ValueError):
        decode_upload(value, ["png"], 5)


def test_removing_file_returns_no_upload():
    assert decode_upload(None, ["png"], 100) is None
