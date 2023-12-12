################################################################################
# viewmaster_config.py
################################################################################

import platform
import socket
import sys

# Test for a command line run
VIEWMASTER_TESTING = ('flask' in sys.argv[0] or 'ipython' in sys.argv[0])
VIEWMASTER_FOR_MARK = ('mark' in socket.gethostname().lower() or
                       'local' in socket.gethostname().lower())

# For command-line testing and development
if VIEWMASTER_TESTING:
    LOCALHOST_ = 'http://localhost/'
    VIEWMASTER_PREFIX_ = 'http://127.0.0.1:5000/'
    WEBSITE_HTTP_HOME = 'http://localhost'
    LOGNAME = 'pds.viewmaster.testing'
    VIEWMASTER_MEMCACHE_PORT = 0
    PDSFILE_MEMCACHE_PORT = 0
    MAKE_SYMLINKS = False
    PAGE_CACHING = False

# For testing on mark.local
elif VIEWMASTER_FOR_MARK:
    LOCALHOST_ = 'https://mark.local/'
    VIEWMASTER_PREFIX_ = 'https://mark.local/viewmaster/'
    WEBSITE_HTTP_HOME = 'https://mark.local'
    LOGNAME = 'pds.viewmaster.local'
    VIEWMASTER_MEMCACHE_PORT = '/var/tmp/memcached.socket'
    PDSFILE_MEMCACHE_PORT = '/var/tmp/memcached.socket'
    MAKE_SYMLINKS = True
    PAGE_CACHING = False

# As deployed
else:
    LOCALHOST_ = '/'
    VIEWMASTER_PREFIX_ = LOCALHOST_ + 'viewmaster/'
    WEBSITE_HTTP_HOME = 'https://pds-rings.seti.org'
    LOGNAME = 'pds.viewmaster.server'
    MAKE_SYMLINKS = True
    PAGE_CACHING = False

if platform.system() == 'Linux':
    VIEWMASTER_MEMCACHE_PORT = '/var/run/memcached/memcached.socket'
    PDSFILE_MEMCACHE_PORT = '/var/run/memcached/memcached.socket'
    WEBSITE_ROOT_ = '/var/www/'
    DOCUMENT_ROOT_ = '/var/www/documents/'
    LOG_ROOT_PREFIX_ = '/var/www/logs/webapps/'
    HTTPD_CUSTOMIZATION = '/etc/apache2/site-customization.conf'
    EXTRA_LOCAL_IP_ADDRESS_A_B_C = '10.1.10.'
else:
    VIEWMASTER_MEMCACHE_PORT = '/var/tmp/memcached.socket'
    PDSFILE_MEMCACHE_PORT = '/var/tmp/memcached.socket'
    WEBSITE_ROOT_ = '/Library/WebServer/'
    DOCUMENT_ROOT_ = '/Library/WebServer/Documents/'
    LOG_ROOT_PREFIX_ = '/Library/WebServer/Logs/webapps/'
    HTTPD_CUSTOMIZATION = '/usr/local/etc/httpd/httpd_customization.conf'
    EXTRA_LOCAL_IP_ADDRESS_A_B_C = None

USE_SHELVES_ONLY = False

################################################################################
