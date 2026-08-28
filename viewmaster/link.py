"""Link redirect service for PDS files and directories.

This module provides a simple Flask application that redirects requests to
either Viewmaster (for directories) or directly to the file location (for files).
It serves as a lightweight routing layer that determines whether a requested path is
a directory or file and redirects accordingly.

The service:
    * Detects directories by checking if the basename has no extension or ends
      with a digit (version suffix)
    * Redirects directories to Viewmaster for proper rendering
    * Redirects files to WEBSITE_HTTP_HOME/holdings/... after confirming the
      file exists under PDS3_HOLDINGS_DIR
"""

from flask import Blueprint, Flask, redirect, abort

import os
import logging
import pdslogger

link_bp = Blueprint('link', __name__)

from .viewmaster_config import (
    LOGNAME,
    LOG_ROOT_PREFIX_,
    VIEWMASTER_PREFIX_,
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

    log_file = LOG_ROOT_PREFIX_ + 'link.log'
    info_logfile = os.path.abspath(log_file)

    try:
        info_handler = pdslogger.file_handler(info_logfile, level=logging.INFO,
                                              rotation='midnight')
        logger.add_handler(info_handler)
    except OSError as e:
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


@link_bp.route('/', defaults={'query_path': 'volumes'})
@link_bp.route('/<path:query_path>')
def link(query_path):
    """Route handler that redirects requests to appropriate destinations.

    Determines whether the requested path is a directory or file and redirects
    accordingly:

        * Directories are redirected to Viewmaster for proper rendering
        * Files are redirected to WEBSITE_HTTP_HOME/holdings/<query_path> if
          the file exists under PDS3_HOLDINGS_DIR

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
            404 error if PDS3_HOLDINGS_DIR is unset or the file is not found
            under that directory.
    """

    logger = get_or_create_logger()

    original_query_path = query_path
    query_path = query_path.split('?')[0]

    # We recognize a file path as something with an extension, but ignore
    # version suffixes like "_v1.0". This is consistent with anything our
    # website would link to.
    basename = os.path.basename(query_path)
    parts = basename.split('.')

    isdir = len(parts) == 1 or parts[-1].isdigit()
    if isdir:
        logger.info('Redirect to Viewmaster', original_query_path)
        return redirect(VIEWMASTER_PREFIX_ + original_query_path)

    else:
        logger.info('Redirect to file', query_path)
        holdings_dir = os.getenv('PDS3_HOLDINGS_DIR', '')
        abspath = os.path.join(holdings_dir, query_path)
        if not holdings_dir or not os.path.isfile(abspath):
            logger.error('File not found:', abspath)
            abort(404)

        return redirect(WEBSITE_HTTP_HOME + '/holdings/' + query_path)

def create_app():
    """Create and configure the Flask application for the Link service.

    Initializes a Flask app instance and registers the link blueprint that
    handles routing for PDS file and directory redirects.

    Returns:
        Flask: Configured Flask application instance with the link blueprint
            registered.
    """

    app = Flask(__name__)
    app.register_blueprint(link_bp)

    return app

################################################################################
