"""Configuration module for Viewmaster web application.

This module sets up environment-specific configuration for the Viewmaster Flask
application. It detects whether Viewmaster is running in testing mode
(``VIEWMASTER_TESTING`` env var, or ``python -m viewmaster.viewmaster`` / the
``viewmaster`` CLI) or production mode, and sets appropriate paths, URLs,
caching options, and logging configuration based on the platform (Linux vs
macOS) and execution context.

Hard-coded production defaults can be overridden with environment variables
(see Configuration Variables). In testing mode, log files go under
``$XDG_STATE_HOME/viewmaster/`` (or ``~/.local/state/viewmaster/``) so local
development does not require creating ``/var/www`` or ``/Library/WebServer``.

The module defines configuration variables that are imported by `viewmaster.py`:
    * URL prefixes and paths for localhost and web server
    * Memcache socket paths for page and PdsFile caching
    * Filesystem paths for documents and logs
    * Logging configuration names
    * Caching flags
    * Platform-specific IP address ranges

Configuration Variables:
    * ``VIEWMASTER_TESTING`` (bool): True in local-dev/testing mode. Set by
      ``VIEWMASTER_TESTING=1`` (or ``true``/``yes``). ``0``/``false``/``no``
      force production config. When unset, inferred when ``sys.argv[0]`` is
      the ``viewmaster`` CLI or ends with ``viewmaster.py`` (covers
      ``python -m viewmaster.viewmaster``). ``flask run``, gunicorn, and
      pytest must set the env var.
    * ``LOCALHOST_`` (str): Localhost URL prefix, typically '/'.
    * ``VIEWMASTER_PREFIX_`` (str): Full URL prefix for Viewmaster routes.
      Override with ``VIEWMASTER_URL_PREFIX``.
    * ``WEBSITE_HTTP_HOME`` (str): Base URL for the website. Override with
      ``VIEWMASTER_WEBSITE_HTTP_HOME``.
    * ``LOGNAME`` (str): Logger name for pdslogger.
    * ``VIEWMASTER_MEMCACHE_PORT`` (str|int): Memcache socket path or 0 to
      disable. Override with ``VIEWMASTER_MEMCACHE_PORT``.
    * ``PDSFILE_MEMCACHE_PORT`` (str|int): Memcache socket path for PdsFile
      cache or 0. Override with ``PDSFILE_MEMCACHE_PORT``.
    * ``PAGE_CACHING`` (bool): Whether to enable page-level caching.
    * ``DOCUMENT_ROOT_`` (str): Root directory for document files. Override
      with ``VIEWMASTER_DOCUMENT_ROOT``.
    * ``LOG_ROOT_PREFIX_`` (str): Root directory prefix for log files.
      Override with ``VIEWMASTER_LOG_DIR``.
    * ``EXTRA_LOCAL_IP_ADDRESS_A_B_C`` (str|None): Additional local IP prefix
      for cache building, or None. Override with ``VIEWMASTER_EXTRA_LOCAL_IP``.
    * ``USE_SHELVES_ONLY`` (bool): Whether to use shelves-only mode for Pds3File.
"""

import os
import platform
import sys

# Primary signal is VIEWMASTER_TESTING (1/true/yes vs 0/false/no). When unset,
# fall back to the `viewmaster` CLI / `python -m viewmaster.viewmaster`.
# flask run, gunicorn, and pytest must set the env var explicitly.
_argv0 = os.path.basename(sys.argv[0])
_argv0_stem = os.path.splitext(_argv0)[0]
_testing_env = os.getenv('VIEWMASTER_TESTING', '')
if _testing_env != '':
    VIEWMASTER_TESTING = _testing_env.lower() in ('1', 'true', 'yes')
else:
    VIEWMASTER_TESTING = (
        _argv0.endswith('viewmaster.py')
        or _argv0_stem == 'viewmaster'
    )


def _with_trailing_slash(path):
    if not path:
        return path
    return path if path.endswith(os.sep) or path.endswith('/') else path + '/'


def _env_or(name, default):
    value = os.getenv(name)
    return default if value is None or value == '' else value


def _memcache_from_env(name, default):
    """Return an env-var memcache target, or *default* if unset.

    ``0``, ``false``, ``no``, or ``''`` disable memcache (port 0). Digit
    strings are returned as ``int``; anything else is treated as a socket path.
    """
    value = os.getenv(name)
    if value is None:
        return default
    if value.lower() in ('0', 'false', 'no', ''):
        return 0
    if value.isdigit():
        return int(value)
    return value


def _testing_log_dir():
    """Writable log directory for local-dev/testing mode (no sudo required)."""
    explicit = os.getenv('VIEWMASTER_LOG_DIR')
    if explicit:
        return _with_trailing_slash(explicit)
    xdg = os.getenv('XDG_STATE_HOME')
    if xdg:
        return _with_trailing_slash(os.path.join(xdg, 'viewmaster'))
    return _with_trailing_slash(
        os.path.join(os.path.expanduser('~'), '.local', 'state', 'viewmaster')
    )


# For command-line testing and development
if VIEWMASTER_TESTING:
    LOCALHOST_ = '/'
    VIEWMASTER_PREFIX_ = 'http://127.0.0.1:8080/'
    WEBSITE_HTTP_HOME = 'http://localhost'
    LOGNAME = 'pds.viewmaster.testing'
    VIEWMASTER_MEMCACHE_PORT = 0
    PDSFILE_MEMCACHE_PORT = 0
    PAGE_CACHING = False
    LOG_ROOT_PREFIX_ = _testing_log_dir()
# As deployed
else:
    LOCALHOST_ = '/'
    VIEWMASTER_PREFIX_ = LOCALHOST_ + 'viewmaster/'
    WEBSITE_HTTP_HOME = 'https://pds-rings.seti.org'
    LOGNAME = 'pds.viewmaster.server'
    PAGE_CACHING = False
    LOG_ROOT_PREFIX_ = None

if platform.system() == 'Linux':
    if not VIEWMASTER_TESTING:
        VIEWMASTER_MEMCACHE_PORT = '/var/run/memcached/memcached.socket'
        PDSFILE_MEMCACHE_PORT = '/var/run/memcached/memcached.socket'
        LOG_ROOT_PREFIX_ = '/var/www/logs/webapps/'
    # else: keep ports at 0 and LOG_ROOT_PREFIX_ from testing block above
    DOCUMENT_ROOT_ = '/var/www/documents/'
    EXTRA_LOCAL_IP_ADDRESS_A_B_C = '10.1.10.'
else:
    if VIEWMASTER_TESTING:
        VIEWMASTER_MEMCACHE_PORT = 0
        PDSFILE_MEMCACHE_PORT = 0
    else:
        VIEWMASTER_MEMCACHE_PORT = '/var/tmp/memcached.socket'
        PDSFILE_MEMCACHE_PORT = '/var/tmp/memcached.socket'
        LOG_ROOT_PREFIX_ = '/Library/WebServer/Logs/webapps/'

    DOCUMENT_ROOT_ = '/Library/WebServer/Documents/'
    EXTRA_LOCAL_IP_ADDRESS_A_B_C = None

# Environment overrides (empty/unset leaves the platform default).
DOCUMENT_ROOT_ = _with_trailing_slash(
    _env_or('VIEWMASTER_DOCUMENT_ROOT', DOCUMENT_ROOT_)
)
if not VIEWMASTER_TESTING:
    LOG_ROOT_PREFIX_ = _with_trailing_slash(
        _env_or('VIEWMASTER_LOG_DIR', LOG_ROOT_PREFIX_)
    )
WEBSITE_HTTP_HOME = _env_or('VIEWMASTER_WEBSITE_HTTP_HOME', WEBSITE_HTTP_HOME)
VIEWMASTER_PREFIX_ = _env_or('VIEWMASTER_URL_PREFIX', VIEWMASTER_PREFIX_)
if VIEWMASTER_PREFIX_ and not VIEWMASTER_PREFIX_.endswith('/'):
    VIEWMASTER_PREFIX_ += '/'

VIEWMASTER_MEMCACHE_PORT = _memcache_from_env(
    'VIEWMASTER_MEMCACHE_PORT', VIEWMASTER_MEMCACHE_PORT
)
PDSFILE_MEMCACHE_PORT = _memcache_from_env(
    'PDSFILE_MEMCACHE_PORT', PDSFILE_MEMCACHE_PORT
)

_extra_ip = os.getenv('VIEWMASTER_EXTRA_LOCAL_IP')
if _extra_ip is not None:
    EXTRA_LOCAL_IP_ADDRESS_A_B_C = _extra_ip or None

USE_SHELVES_ONLY = False

if VIEWMASTER_TESTING and LOG_ROOT_PREFIX_:
    try:
        os.makedirs(LOG_ROOT_PREFIX_, exist_ok=True)
    except OSError:
        pass

################################################################################
