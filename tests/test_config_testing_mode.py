"""Tests for VIEWMASTER_TESTING detection, path overrides, and secret-key loading."""

import importlib
import os
import sys
from unittest.mock import patch

import pytest

import viewmaster.viewmaster_config as config

_OVERRIDE_KEYS = (
    'VIEWMASTER_TESTING',
    'VIEWMASTER_LOG_DIR',
    'VIEWMASTER_DOCUMENT_ROOT',
    'VIEWMASTER_WEBSITE_HTTP_HOME',
    'VIEWMASTER_URL_PREFIX',
    'VIEWMASTER_MEMCACHE_PORT',
    'PDSFILE_MEMCACHE_PORT',
    'VIEWMASTER_EXTRA_LOCAL_IP',
    'XDG_STATE_HOME',
)


def _reload_config(*, testing_env=None, argv=None, system=None, extra_env=None):
    """Reload viewmaster_config under the given env, argv, and platform."""
    env = os.environ.copy()
    for key in _OVERRIDE_KEYS:
        env.pop(key, None)
    if testing_env is None:
        env.pop('VIEWMASTER_TESTING', None)
    else:
        env['VIEWMASTER_TESTING'] = testing_env
    if extra_env:
        env.update(extra_env)

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
    assert not cfg.LOG_ROOT_PREFIX_.startswith('/var/www')
    assert not cfg.LOG_ROOT_PREFIX_.startswith('/Library')


@pytest.mark.parametrize('value', ['true', 'TRUE', 'yes', 'Yes'])
def test_testing_env_true_aliases(value):
    cfg = _reload_config(testing_env=value, argv=['pytest'])
    assert cfg.VIEWMASTER_TESTING is True


def test_testing_env_false_without_argv_fallback():
    cfg = _reload_config(testing_env='0', argv=['gunicorn'])
    assert cfg.VIEWMASTER_TESTING is False


def test_testing_env_false_overrides_argv_fallback():
    cfg = _reload_config(testing_env='0', argv=['/path/to/viewmaster.py'])
    assert cfg.VIEWMASTER_TESTING is False


def test_argv_fallback_enables_testing_mode():
    cfg = _reload_config(testing_env=None, argv=['/path/to/viewmaster.py'])
    assert cfg.VIEWMASTER_TESTING is True


def test_cli_basename_enables_testing_mode():
    cfg = _reload_config(testing_env=None, argv=['/usr/local/bin/viewmaster'])
    assert cfg.VIEWMASTER_TESTING is True


def test_linux_production_uses_memcache_socket():
    cfg = _reload_config(testing_env=None, argv=['gunicorn'], system='Linux')
    assert cfg.VIEWMASTER_TESTING is False
    assert cfg.VIEWMASTER_MEMCACHE_PORT == '/var/run/memcached/memcached.socket'
    assert cfg.PDSFILE_MEMCACHE_PORT == '/var/run/memcached/memcached.socket'
    assert cfg.LOG_ROOT_PREFIX_ == '/var/www/logs/webapps/'
    assert cfg.DOCUMENT_ROOT_ == '/var/www/documents/'
    assert cfg.WEBSITE_HTTP_HOME == 'https://pds-rings.seti.org'


def test_testing_log_dir_uses_xdg_state_home(tmp_path):
    xdg = tmp_path / 'xdg-state'
    cfg = _reload_config(
        testing_env='1',
        argv=['pytest'],
        extra_env={'XDG_STATE_HOME': str(xdg)},
    )
    assert cfg.LOG_ROOT_PREFIX_ == str(xdg / 'viewmaster') + '/'
    assert (xdg / 'viewmaster').is_dir()


def test_viewmaster_log_dir_override_in_testing(tmp_path):
    log_dir = tmp_path / 'custom-logs'
    cfg = _reload_config(
        testing_env='1',
        argv=['pytest'],
        extra_env={'VIEWMASTER_LOG_DIR': str(log_dir)},
    )
    assert cfg.LOG_ROOT_PREFIX_ == str(log_dir) + '/'
    assert log_dir.is_dir()


def test_production_path_env_overrides(tmp_path):
    log_dir = tmp_path / 'prod-logs'
    docs = tmp_path / 'docs'
    cfg = _reload_config(
        testing_env=None,
        argv=['gunicorn'],
        system='Linux',
        extra_env={
            'VIEWMASTER_LOG_DIR': str(log_dir),
            'VIEWMASTER_DOCUMENT_ROOT': str(docs),
            'VIEWMASTER_WEBSITE_HTTP_HOME': 'https://example.test',
            'VIEWMASTER_URL_PREFIX': '/vm',
            'VIEWMASTER_MEMCACHE_PORT': '0',
            'PDSFILE_MEMCACHE_PORT': '/tmp/pdsfile.sock',
            'VIEWMASTER_EXTRA_LOCAL_IP': '192.168.1.',
        },
    )
    assert cfg.LOG_ROOT_PREFIX_ == str(log_dir) + '/'
    assert cfg.DOCUMENT_ROOT_ == str(docs) + '/'
    assert cfg.WEBSITE_HTTP_HOME == 'https://example.test'
    assert cfg.VIEWMASTER_PREFIX_ == '/vm/'
    assert cfg.VIEWMASTER_MEMCACHE_PORT == 0
    assert cfg.PDSFILE_MEMCACHE_PORT == '/tmp/pdsfile.sock'
    assert cfg.EXTRA_LOCAL_IP_ADDRESS_A_B_C == '192.168.1.'


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
