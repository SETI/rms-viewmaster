"""Link redirect service for PDS files and directories.

This module provides a simple Flask application that redirects requests to
either Viewmaster (for directories) or directly to the file location (for files).
It serves as a lightweight routing layer that determines whether a requested path is
a directory or file and redirects accordingly.

The service:
    * Detects directories by checking if the basename has no extension or ends
      with a digit (version suffix)
    * Redirects directories to Viewmaster for proper rendering
    * Redirects files to their actual location in the holdings directories
    * Uses glob patterns to locate files across multiple holdings symlinks
"""

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

from .viewmaster_config import (
    LOGNAME,
    LOG_ROOT_PREFIX_,
    VIEWMASTER_PREFIX_,
    DOCUMENT_ROOT_,
    WEBSITE_HTTP_HOME
)

# Module-level logger cache
LOGGER = None

def create_logger():
    """Create and configure a logger for the Link service.

    Sets up a PdsLogger instance with INFO level logging to a file with
    midnight rotation. The logger name is derived from the Viewmaster logger
    name by replacing 'viewmaster' with 'link'.

    Returns:
        pdslogger.PdsLogger: Configured logger instance.
    """

    link_logger_name = LOGNAME.replace('viewmaster', 'link')
    logger = pdslogger.PdsLogger(link_logger_name, limits={'info': -1, 'normal': -1},
                                 pid=True)

    LOG_FILE = LOG_ROOT_PREFIX_ + 'link.log'
    info_logfile = os.path.abspath(LOG_FILE)

    try:
        info_handler = pdslogger.file_handler(info_logfile, level=logging.INFO,
                                              rotation='midnight')
        logger.add_handler(info_handler)
    except (OSError, IOError) as e:
        logger.warning(f'Could not open log file {info_logfile}: {e}')

    # DEBUG_LOG_FILE = LOG_ROOT_PREFIX_ + 'link_debug.log'
    # debug_logfile = os.path.abspath(DEBUG_LOG_FILE)
    # debug_handler = pdslogger.file_handler(debug_logfile, level=logging.DEBUG,
    #                                        rotation='midnight')
    # logger.add_handler(debug_handler)

    ################################################################################

    logger.blankline()
    logger.blankline()
    logger.info('Starting Link', info_logfile)

    return logger

def get_or_create_logger():
    """Get the cached logger instance, creating it if necessary.

    This ensures the logger and its handlers are only created once, preventing
    duplicate handlers from being added on subsequent requests.

    Returns:
        pdslogger.PdsLogger: The cached logger instance.
    """
    global LOGGER
    if LOGGER is None:
        LOGGER = create_logger()
    return LOGGER


@app.route('/', defaults={'query_path': 'volumes'})
@app.route('/<path:query_path>')
def link(query_path):
    """Route handler that redirects requests to appropriate destinations.

    Determines whether the requested path is a directory or file and redirects
    accordingly:

        * Directories are redirected to Viewmaster for proper rendering
        * Files are redirected to their actual location in holdings

    Directory detection is based on whether the basename has no extension or
    ends with a digit (version suffix like "_v1.0").

    Parameters:
        query_path (str):
            The requested path, which may include query parameters that will be stripped.

    Returns:
        werkzeug.wrappers.response.Response:
            Redirect response to either Viewmaster (for directories) or the file
            location (for files).

    Raises:
        werkzeug.exceptions.NotFound:
            404 error if the file is not found in any holdings directory.

    """

    logger = get_or_create_logger()

    original_query_path = query_path
    query_path = query_path.split('?')[0]

    # We recognize a file path as something with an extension, but ignore
    # version suffixes like "_v1.0". This is way faster than a glob.glob call,
    # and is consistent with anything our website would link to.
    basename = os.path.basename(query_path)
    parts = basename.split('.')

    isdir = len(parts) == 1 or parts[-1].isdigit()
    if isdir:
        logger.info('Redirect to Viewmaster', original_query_path)
        return redirect(VIEWMASTER_PREFIX_ + original_query_path)

    else:
        logger.info('Redirect to file', query_path)
        pattern = DOCUMENT_ROOT_ + '/holdings*/' + query_path
        abspaths = glob.glob(pattern)
        if not abspaths:
            logger.error('File not found:', pattern)
            abort(404)

        abspath = abspaths[0]
        parts = abspath.partition('/holdings')
        return redirect(WEBSITE_HTTP_HOME + parts[1] + parts[2])

################################################################################
