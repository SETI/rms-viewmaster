"""Tests for PDS4_HOLDINGS_DIR validation and loading."""

import os
from unittest.mock import MagicMock, patch

import pytest

from viewmaster.viewmaster import (
    get_holdings_path,
    get_holdings_paths,
    get_pds4_holdings_path,
    validate_pds4_holdings_path,
)


def _make_pds3_tree(tmp_path):
    prefix = tmp_path / 'pds3'
    prefix.mkdir()
    (prefix / 'holdings').mkdir()
    return prefix / 'holdings'


def _make_pds4_tree(tmp_path):
    holdings = tmp_path / 'pds4-holdings'
    holdings.mkdir()
    return holdings


def test_get_pds4_holdings_path_unset():
    env = os.environ.copy()
    env.pop('PDS4_HOLDINGS_DIR', None)
    with patch.dict(os.environ, env, clear=True):
        assert get_pds4_holdings_path() is None


def test_get_pds4_holdings_path_set(tmp_path):
    with patch.dict(os.environ, {'PDS4_HOLDINGS_DIR': str(tmp_path)}):
        assert get_pds4_holdings_path() == str(tmp_path)


def test_validate_pds4_accepts_named_directory(tmp_path):
    holdings = _make_pds4_tree(tmp_path)
    logger = MagicMock()
    assert validate_pds4_holdings_path(str(holdings), logger) == str(holdings)
    logger.fatal.assert_not_called()
    logger.error.assert_not_called()


def test_validate_pds4_rejects_wrong_basename(tmp_path):
    other = tmp_path / 'holdings'
    other.mkdir()
    logger = MagicMock()
    with pytest.raises(OSError, match='must be named pds4-holdings'):
        validate_pds4_holdings_path(str(other), logger)
    logger.error.assert_called()


def test_validate_pds4_rejects_missing_path(tmp_path):
    missing = tmp_path / 'pds4-holdings'
    logger = MagicMock()
    with pytest.raises(OSError, match='PDS4 holdings not found'):
        validate_pds4_holdings_path(str(missing), logger)
    logger.fatal.assert_called()


@patch('viewmaster.viewmaster.BOOT_TIME', 0)
def test_get_holdings_path_loads_optional_pds4(tmp_path):
    pds3 = _make_pds3_tree(tmp_path)
    pds4 = _make_pds4_tree(tmp_path)
    logger = MagicMock()
    env = {
        'PDS3_HOLDINGS_DIR': str(pds3),
        'PDS4_HOLDINGS_DIR': str(pds4),
    }
    with patch.dict(os.environ, env, clear=False):
        paths = get_holdings_path(logger)

    from viewmaster import viewmaster as vm
    assert paths == [str(pds3)]
    assert vm.PDS4_HOLDINGS_PATHS == [str(pds4)]


@patch('viewmaster.viewmaster.BOOT_TIME', 0)
def test_get_holdings_path_without_pds4(tmp_path):
    pds3 = _make_pds3_tree(tmp_path)
    logger = MagicMock()
    env = os.environ.copy()
    env['PDS3_HOLDINGS_DIR'] = str(pds3)
    env.pop('PDS4_HOLDINGS_DIR', None)
    with patch.dict(os.environ, env, clear=True):
        paths = get_holdings_path(logger)

    from viewmaster import viewmaster as vm
    assert paths == [str(pds3)]
    assert vm.PDS4_HOLDINGS_PATHS == []


def test_get_holdings_paths_still_requires_pds3():
    env = os.environ.copy()
    env.pop('PDS3_HOLDINGS_DIR', None)
    env['PDS4_HOLDINGS_DIR'] = '/tmp/pds4-holdings'
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(OSError, match='PDS3_HOLDINGS_DIR'):
            get_holdings_paths()


@patch('viewmaster.viewmaster.Pds4File.preload')
@patch('viewmaster.viewmaster.Pds3File.preload')
def test_initialize_caches_preloads_pds4(mock_pds3, mock_pds4):
    from viewmaster import viewmaster as vm

    logger = MagicMock()
    with patch.object(vm, 'LOGGER', logger), \
         patch.object(vm, 'HOLDINGS_PATHS', ['/data/holdings']), \
         patch.object(vm, 'PDS4_HOLDINGS_PATHS', ['/data/pds4-holdings']), \
         patch.object(vm, 'PAGE_CACHE', None):
        vm.initialize_caches(reset=False)

    logger.replace_root.assert_called_once_with(
        ['/data/holdings', '/data/pds4-holdings']
    )
    mock_pds3.assert_called_once()
    mock_pds4.assert_called_once()
    assert mock_pds4.call_args[0][0] == ['/data/pds4-holdings']
