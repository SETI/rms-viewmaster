from flask import Flask, redirect, abort

import os
import glob
import logging
import pdslogger

app = Flask(__name__)

################################################################################
# Define...
#     LOCALHOST_ = '/'
#     VIEWMASTER_PREFIX_ = LOCALHOST_ + 'viewmaster/' 
#     WEBSITE_HTTP_HOME = 'https://pds-rings.seti.org'
#     LOGNAME = 'pds.viewmaster.server'
#     VIEWMASTER_MEMCACHE_PORT = '/var/tmp/memcached.socket'
#     PDSFILE_MEMCACHE_PORT = '/var/tmp/memcached.socket'
#     MAKE_SYMLINKS = True
#     PAGE_CACHING = False
#     WEBSITE_ROOT_ = '/Library/WebServer/'
#     DOCUMENT_ROOT_ = '/Library/WebServer/Documents/'
#     LOG_ROOT_PREFIX_ = '/Library/WebServer/Logs/webapps/'
################################################################################

from viewmaster_config import *

LOGNAME = LOGNAME.replace('viewmaster', 'link')
LOGGER = pdslogger.PdsLogger(LOGNAME, limits={'info': -1, 'normal': -1},
                                      pid=True)

LOG_FILE = LOG_ROOT_PREFIX_ + 'link.log'
info_logfile = os.path.abspath(LOG_FILE)
info_handler = pdslogger.file_handler(info_logfile, level=logging.INFO,
                                      rotation='midnight')
LOGGER.add_handler(info_handler)

# DEBUG_LOG_FILE = LOG_ROOT_PREFIX_ + 'link_debug.log'
# debug_logfile = os.path.abspath(DEBUG_LOG_FILE)
# debug_handler = pdslogger.file_handler(debug_logfile, level=logging.DEBUG,
#                                        rotation='midnight')
# LOGGER.add_handler(debug_handler)

################################################################################

LOGGER.blankline()
LOGGER.blankline()
LOGGER.info('Starting Link', info_logfile)

@app.route('/', defaults={'query_path': 'volumes'})
@app.route('/<path:query_path>')
def link(query_path):
    """Redirects directly to a file; redirects to Viewmaster for a directory."""

    global LOGGER

    original_query_path = query_path
    query_path = query_path.split('?')[0]

    # We recognize a file path as something with an extension, but ignore
    # version suffixes like "_v1.0". This is way faster than a glob.glob call,
    # and is consistent with anything our website would link to.
    basename = os.path.basename(query_path)
    parts = basename.split('.')

    isdir = len(parts) == 1 or parts[-1].isdigit()
    if isdir:
        LOGGER.info('Redirect to Viewmaster', original_query_path)
        return redirect(VIEWMASTER_PREFIX_ + original_query_path)

    else:
        LOGGER.info('Redirect to file', query_path)
        pattern = DOCUMENT_ROOT_ + '/holdings*/' + query_path
        abspaths = glob.glob(pattern)
        if not abspaths:
            LOGGER.error('File not found:', pattern)
            abort(404)

        abspath = abspaths[0]
        parts = abspath.partition('/holdings')
        return redirect(WEBSITE_HTTP_HOME + parts[1] + parts[2])

################################################################################
