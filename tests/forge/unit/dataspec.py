"""Helpers for the data-loader tests: write a JSON file, load it, keep the message."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from invoice_forge.jsonspec import SpecError


def write(tmp_path: Path, name: str, data: object) -> str:
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def message(load: Callable[[str], Any], tmp_path: Path, name: str, data: object) -> str:
    """The `SpecError` message `load` raises for this data, as a string."""
    with pytest.raises(SpecError) as raised:
        load(write(tmp_path, name, data))
    return str(raised.value)
