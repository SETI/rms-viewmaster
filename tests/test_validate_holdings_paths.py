"""Unit tests for validate_holdings_paths()."""

from unittest.mock import MagicMock, patch

import pytest

from viewmaster.viewmaster import validate_holdings_paths


def _make_holdings_dir(tmp_path, *, holdings_is_dir=True):
    """Create a holdings path and return it as PDS3_HOLDINGS_DIR would be set."""
    prefix = tmp_path / 'prefix'
    prefix.mkdir()
    holdings = prefix / 'holdings'
    if holdings_is_dir:
        holdings.mkdir()
    else:
        holdings.write_text('not a directory')
    return str(holdings)


@patch('viewmaster.viewmaster.BOOT_TIME', 0)
def test_valid_holdings_dir_is_accepted(tmp_path):
    holdings = _make_holdings_dir(tmp_path)
    logger = MagicMock()

    result = validate_holdings_paths([holdings], logger)

    assert result == [holdings]
    logger.fatal.assert_not_called()


@patch('viewmaster.viewmaster.BOOT_TIME', 0)
def test_path_not_named_holdings_is_rejected(tmp_path):
    other = tmp_path / 'other'
    other.mkdir()
    logger = MagicMock()

    with pytest.raises(OSError, match='Holdings list is empty'):
        validate_holdings_paths([str(other)], logger)

    logger.error.assert_called()
    assert 'Not a holdings directory' in logger.error.call_args[0][0]


@patch('viewmaster.viewmaster.BOOT_TIME', 0)
def test_holdings_file_is_logged_but_still_accepted(tmp_path):
    holdings = _make_holdings_dir(tmp_path, holdings_is_dir=False)
    logger = MagicMock()

    result = validate_holdings_paths([holdings], logger)

    assert result == [holdings]
    logger.error.assert_called()
    assert 'Not a directory' in logger.error.call_args[0][0]


@patch('viewmaster.viewmaster.BOOT_TIME', 0)
def test_missing_path_is_skipped(tmp_path):
    missing = str(tmp_path / 'prefix' / 'holdings')
    logger = MagicMock()

    with pytest.raises(OSError, match='Holdings list is empty'):
        validate_holdings_paths([missing], logger)

    logger.fatal.assert_called_once()
    assert 'Holdings not found' in logger.fatal.call_args[0][0]
