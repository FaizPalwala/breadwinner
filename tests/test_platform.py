"""Tests for cross-platform system helpers."""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from breadwinner.core.platform import open_path


def test_open_path_darwin(tmp_path: Path):
    target = tmp_path / "sample_folder"
    target.mkdir()

    with patch("platform.system", return_value="Darwin"):
        with patch("subprocess.run") as mock_run:
            res = open_path(target)
            assert res is True
            mock_run.assert_called_once_with(["open", str(target.resolve())], check=False)


def test_open_path_windows_startfile(tmp_path: Path):
    target = tmp_path / "sample_folder"
    target.mkdir()

    mock_startfile = MagicMock()
    with patch("platform.system", return_value="Windows"):
        with patch.object(os, "startfile", mock_startfile, create=True):
            res = open_path(target)
            assert res is True
            mock_startfile.assert_called_once_with(str(target.resolve()))


def test_open_path_windows_fallback(tmp_path: Path):
    target = tmp_path / "sample_folder"
    target.mkdir()

    mock_startfile = MagicMock(side_effect=OSError("No association"))
    with patch("platform.system", return_value="Windows"):
        with patch.object(os, "startfile", mock_startfile, create=True):
            with patch("subprocess.run") as mock_run:
                res = open_path(target)
                assert res is True
                mock_run.assert_called_once_with(["explorer", str(target.resolve())], check=False)


def test_open_path_linux(tmp_path: Path):
    target = tmp_path / "sample_folder"
    target.mkdir()

    with patch("platform.system", return_value="Linux"):
        with patch("subprocess.run") as mock_run:
            res = open_path(target)
            assert res is True
            mock_run.assert_called_once_with(["xdg-open", str(target.resolve())], check=False)


def test_open_path_handles_exception():
    with patch("platform.system", return_value="Darwin"):
        with patch("subprocess.run", side_effect=Exception("Failed")):
            res = open_path("/non/existent/path")
            assert res is False
