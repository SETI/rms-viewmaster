"""Unit tests for validate_holdings_paths() sibling-directory checks."""

from unittest.mock import MagicMock, patch

import pytest

from viewmaster.viewmaster import validate_holdings_paths


def _make_holdings_tree(tmp_path, *, shelves=True, volinfo=True, holdings_is_dir=True):
    """Create a prefix with the holdings/shelves/volinfo layout.

    Returns the path that should be passed as PDS3_HOLDINGS_DIR (the holdings
    directory itself).
    """
    prefix = tmp_path / 'prefix'
    prefix.mkdir()
    holdings = prefix / 'holdings'
    if holdings_is_dir:
        holdings.mkdir()
    else:
        holdings.write_text('not a directory')
    if shelves:
        (prefix / 'shelves').mkdir()
    if volinfo:
        (prefix / 'volinfo').mkdir()
    return str(holdings)


@patch('viewmaster.viewmaster.BOOT_TIME', 0)
def test_missing_shelves_rejects_path(tmp_path):
    holdings = _make_holdings_tree(tmp_path, shelves=False)
    logger = MagicMock()

    with pytest.raises(OSError, match='Holdings list is empty'):
        validate_holdings_paths([holdings], logger)

    logger.warning.assert_called()
    warning_args = logger.warning.call_args[0]
    assert 'missing or not a directory' in warning_args[0]
    assert warning_args[1].endswith('shelves')


@patch('viewmaster.viewmaster.BOOT_TIME', 0)
def test_missing_volinfo_rejects_path(tmp_path):
    holdings = _make_holdings_tree(tmp_path, volinfo=False)
    logger = MagicMock()

    with pytest.raises(OSError, match='Holdings list is empty'):
        validate_holdings_paths([holdings], logger)

    logger.warning.assert_called()
    warning_args = logger.warning.call_args[0]
    assert warning_args[1].endswith('volinfo')


@patch('viewmaster.viewmaster.BOOT_TIME', 0)
def test_valid_layout_is_accepted(tmp_path):
    holdings = _make_holdings_tree(tmp_path)
    logger = MagicMock()

    result = validate_holdings_paths([holdings], logger)

    assert result == [holdings]
    logger.warning.assert_not_called()
    logger.error.assert_not_called()
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
def test_missing_path_is_skipped(tmp_path):
    missing = str(tmp_path / 'prefix' / 'holdings')
    logger = MagicMock()

    with pytest.raises(OSError, match='Holdings list is empty'):
        validate_holdings_paths([missing], logger)

    logger.fatal.assert_called_once()
    assert 'Holdings not found' in logger.fatal.call_args[0][0]
