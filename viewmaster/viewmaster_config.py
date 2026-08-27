"""Configuration module for Viewmaster web application.

This module sets up environment-specific configuration for the Viewmaster Flask
application. It detects whether Viewmaster is running in testing mode (command-line)
or production mode, and sets appropriate paths, URLs, caching options, and logging
configuration based on the platform (Linux vs macOS) and execution context.

The module defines configuration variables that are imported by `viewmaster.py`:
    * URL prefixes and paths for localhost and web server
    * Memcache socket paths for page and PdsFile caching
    * Filesystem paths for documents and logs
    * Logging configuration names
    * Caching flags
    * Platform-specific IP address ranges

Configuration Variables:
    * ``VIEWMASTER_TESTING`` (bool): True if running from command line.
    * ``LOCALHOST_`` (str): Localhost URL prefix, typically '/'.
    * ``VIEWMASTER_PREFIX_`` (str): Full URL prefix for Viewmaster routes.
    * ``WEBSITE_HTTP_HOME`` (str): Base URL for the website.
    * ``LOGNAME`` (str): Logger name for pdslogger.
    * ``VIEWMASTER_MEMCACHE_PORT`` (str|int): Memcache socket path or 0 to disable.
    * ``PDSFILE_MEMCACHE_PORT`` (str|int): Memcache socket path for PdsFile cache or 0.
    * ``PAGE_CACHING`` (bool): Whether to enable page-level caching.
    * ``DOCUMENT_ROOT_`` (str): Root directory for document files.
    * ``LOG_ROOT_PREFIX_`` (str): Root directory prefix for log files.
    * ``EXTRA_LOCAL_IP_ADDRESS_A_B_C`` (str|None): Additional local IP prefix for cache
      building, or None.
    * ``USE_SHELVES_ONLY`` (bool): Whether to use shelves-only mode for Pds3File.
"""

import platform
import socket
import sys

# Test for a command line run, python viewmaster/viewmaster.py
VIEWMASTER_TESTING = sys.argv[0].endswith('viewmaster.py')

# For command-line testing and development
if VIEWMASTER_TESTING:
    LOCALHOST_ = '/'
    VIEWMASTER_PREFIX_ = 'http://127.0.0.1:8080/'
    WEBSITE_HTTP_HOME = 'http://localhost'
    LOGNAME = 'pds.viewmaster.testing'
    VIEWMASTER_MEMCACHE_PORT = 0
    PDSFILE_MEMCACHE_PORT = 0
    PAGE_CACHING = False
# As deployed
else:
    LOCALHOST_ = '/'
    VIEWMASTER_PREFIX_ = LOCALHOST_ + 'viewmaster/'
    WEBSITE_HTTP_HOME = 'https://pds-rings.seti.org'
    LOGNAME = 'pds.viewmaster.server'
    PAGE_CACHING = False

if platform.system() == 'Linux':
    if not VIEWMASTER_TESTING:
        VIEWMASTER_MEMCACHE_PORT = '/var/run/memcached/memcached.socket'
        PDSFILE_MEMCACHE_PORT = '/var/run/memcached/memcached.socket'
    # else: keep ports at 0 from testing block above
    DOCUMENT_ROOT_ = '/var/www/documents/'
    LOG_ROOT_PREFIX_ = '/var/www/logs/webapps/'
    EXTRA_LOCAL_IP_ADDRESS_A_B_C = '10.1.10.'
else:
    if VIEWMASTER_TESTING:
        VIEWMASTER_MEMCACHE_PORT = 0
        PDSFILE_MEMCACHE_PORT = 0
    else:
        VIEWMASTER_MEMCACHE_PORT = '/var/tmp/memcached.socket'
        PDSFILE_MEMCACHE_PORT = '/var/tmp/memcached.socket'

    DOCUMENT_ROOT_ = '/Library/WebServer/Documents/'
    LOG_ROOT_PREFIX_ = '/Library/WebServer/Logs/webapps/'
    EXTRA_LOCAL_IP_ADDRESS_A_B_C = None

USE_SHELVES_ONLY = False

################################################################################
