"""Tests for VIEWMASTER_TESTING detection and Flask secret-key loading."""

import importlib
import os
import sys
from unittest.mock import patch

import pytest

import viewmaster.viewmaster_config as config


def _reload_config(*, testing_env=None, argv=None, system=None):
    """Reload viewmaster_config under the given env, argv, and platform."""
    env = os.environ.copy()
    if testing_env is None:
        env.pop('VIEWMASTER_TESTING', None)
    else:
        env['VIEWMASTER_TESTING'] = testing_env

    patches = [patch.dict(os.environ, env, clear=True)]
    if argv is not None:
        patches.append(patch.object(sys, 'argv', argv))
    if system is not None:
        patches.append(patch('platform.system', return_value=system))

    started = []
    try:
        for p in patches:
            p.start()
            started.append(p)
        return importlib.reload(config)
    finally:
        for p in reversed(started):
            p.stop()


@pytest.fixture(autouse=True)
def restore_config():
    yield
    importlib.reload(config)


def test_linux_testing_mode_disables_memcache():
    cfg = _reload_config(testing_env='1', argv=['pytest'], system='Linux')
    assert cfg.VIEWMASTER_TESTING is True
    assert cfg.VIEWMASTER_MEMCACHE_PORT == 0
    assert cfg.PDSFILE_MEMCACHE_PORT == 0


@pytest.mark.parametrize('value', ['true', 'TRUE', 'yes', 'Yes'])
def test_testing_env_true_aliases(value):
    cfg = _reload_config(testing_env=value, argv=['pytest'])
    assert cfg.VIEWMASTER_TESTING is True


def test_testing_env_false_without_argv_fallback():
    cfg = _reload_config(testing_env='0', argv=['gunicorn'])
    assert cfg.VIEWMASTER_TESTING is False


def test_argv_fallback_enables_testing_mode():
    cfg = _reload_config(testing_env=None, argv=['/path/to/viewmaster.py'])
    assert cfg.VIEWMASTER_TESTING is True


def test_linux_production_uses_memcache_socket():
    cfg = _reload_config(testing_env=None, argv=['gunicorn'], system='Linux')
    assert cfg.VIEWMASTER_TESTING is False
    assert cfg.VIEWMASTER_MEMCACHE_PORT == '/var/run/memcached/memcached.socket'
    assert cfg.PDSFILE_MEMCACHE_PORT == '/var/run/memcached/memcached.socket'


@patch('viewmaster.viewmaster.init_once')
def test_secret_key_from_env(mock_init):
    with patch.dict(os.environ, {'VIEWMASTER_SECRET_KEY': 'from-env'}):
        from viewmaster.viewmaster import create_app
        app = create_app()
    assert app.secret_key == 'from-env'
    mock_init.assert_called_once()


@patch('viewmaster.viewmaster.init_once')
@patch('viewmaster.viewmaster.VIEWMASTER_TESTING', True)
def test_secret_key_dev_fallback(mock_init):
    env = os.environ.copy()
    env.pop('VIEWMASTER_SECRET_KEY', None)
    with patch.dict(os.environ, env, clear=True):
        from viewmaster.viewmaster import create_app
        app = create_app()
    assert app.secret_key == 'Cassini Grand Finale!'
    mock_init.assert_called_once()


@patch('viewmaster.viewmaster.init_once')
@patch('viewmaster.viewmaster.VIEWMASTER_TESTING', False)
def test_secret_key_required_in_production(mock_init):
    env = os.environ.copy()
    env.pop('VIEWMASTER_SECRET_KEY', None)
    with patch.dict(os.environ, env, clear=True):
        from viewmaster.viewmaster import create_app
        with pytest.raises(RuntimeError, match='VIEWMASTER_SECRET_KEY'):
            create_app()
    mock_init.assert_not_called()
