"""Viewmaster web application.

This module implements the Viewmaster Flask app used to browse PDS3
holdings. It renders directory and product pages, provides navigation across
neighboring items, manages caching, and exposes utility endpoints for
administration.

The app relies on the `pdsfile` library (not included here) for domain logic
around PDS3 files, and uses Jinja2 templates under `viewmaster/templates/` to
render HTML.

Environment
  - `PDS3_HOLDINGS_DIR`: Absolute path to the PDS3 holdings root.

Configuration
  Values are imported from `viewmaster_config.py` to configure logging,
  filesystem locations, caching, and URL prefixes.
"""

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request, send_file,
    send_from_directory
)
from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField
import wtforms

import os, sys
import datetime
import fnmatch
import hashlib
import html
import logging
import mimetypes
import psutil
import pylibmc
import random
import re
import socket
import time
import urllib
import zlib

import pdsfile
from pdsfile import pdscache, Pds3File, pdsviewable
from . import pdsiterator
import pdslogger
import pdstable

from .pdsgroup import PdsGroup
from .pdsgrouptable import PdsGroupTable

pdsfile.DEFAULT_CACHING = 'dir'             # Cache all directories

app = Flask(__name__)
app.secret_key = "Cassini Grand Finale!"    # needed by flask_wtf

LOCAL_IP_ADDRESS = socket.gethostbyname(socket.gethostname())
LOCAL_IP_ADDRESS_A_B_C = LOCAL_IP_ADDRESS.rpartition('.')[0] + '.'

################################################################################
# These are defined in viewmaster_config.py. Values shown here are examples.
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

# from .viewmaster_config import *
from .viewmaster_config import (
    DOCUMENT_ROOT_,
    EXTRA_LOCAL_IP_ADDRESS_A_B_C,
    LOCALHOST_,
    LOGNAME,
    LOG_ROOT_PREFIX_,
    PAGE_CACHING,
    PDSFILE_MEMCACHE_PORT,
    USE_SHELVES_ONLY,
    VIEWMASTER_MEMCACHE_PORT,
    VIEWMASTER_PREFIX_,
    WEBSITE_HTTP_HOME,
)

if USE_SHELVES_ONLY:
    Pds3File.use_shelves_only(True)

LOGGER = None
HOLDINGS_PATHS = None
PAGE_CACHE = None

def create_logger():
    """Create and configure a logger for the Viewmaster service.

    Sets up a PdsLogger instance with INFO and DEBUG level logging to files
    with midnight rotation. If running in an interactive terminal, also adds
    stdout handler. Configures Pds3File to use this logger.

    Returns:
        pdslogger.PdsLogger: Configured logger instance.
    """

    try:
        logger = pdslogger.PdsLogger.get_logger(LOGNAME)
    except KeyError:
        logger = pdslogger.PdsLogger(LOGNAME, limits={'info': -1, 'normal': -1},
                                            pid=True)

    LOG_FILE = LOG_ROOT_PREFIX_ + 'viewmaster.log'
    info_logfile = os.path.abspath(LOG_FILE)

    has_handlers = bool(getattr(logger, "handlers", []))
    if not has_handlers:
        if sys.stdin.isatty():
            logger.add_handler(pdslogger.stdout_handler)
        else:
            try:
                info_handler = pdslogger.file_handler(
                    info_logfile, level=logging.INFO, rotation='midnight'
                )
                logger.add_handler(info_handler)
            except OSError as e:
                logger.warning(f'Could not open log file {info_logfile}: {e}')


    DEBUG_LOG_FILE = LOG_ROOT_PREFIX_ + 'viewmaster_debug.log'

    debug_logfile = os.path.abspath(DEBUG_LOG_FILE)
    try:
        debug_handler = pdslogger.file_handler(debug_logfile, level=logging.DEBUG,
                                               rotation='midnight')
        logger.add_handler(debug_handler)
    except OSError as e:
        logger.warning(f'Could not open log file {debug_logfile}: {e}')

    Pds3File.set_logger(logger)              # Let PdsFile also log

    logger.blankline()
    logger.blankline()
    logger.info('Starting Viewmaster', info_logfile)

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


################################################################################
################################################################################
################################################################################

ICON_ROOT_ = DOCUMENT_ROOT_ + 'icons-local/'
ICON_URL_  = '/icons-local/'
ICON_COLOR = 'blue'

PDS = '//pds.nasa.gov'
LOCALHOST = LOCALHOST_[:-1]
SET_FILTER = VIEWMASTER_PREFIX_ + 'set_filter'
TRIM_HTML = True

# Maximum number of pages in a multi-page directory view
MAX_PAGES = 8

# This defines the rough number of characters that will fit across the page in
# the neighbor navigation bar
MAX_NAV_STRLEN = 50     # Approximately half the number of chars that fit in
                        # a reasonable neighbor-navigation bar
MAX_NAV_COUNT = 4       # Maximum number of parallel links for navigation
NAV_SPACING = 2         # Effective number of spaces between  navigation entries
NAV_DIVISION_STRLEN = 1 # Chars in division between adjacent directories

# This is the limit on the number of products in a table
MIN_ROWS = 100
MAX_ROWS = 1000

# Categories used for associated files
ASSOCIATED_CATEGORIES = {
    'checksums-archives-volumes'   : ['archives-volumes'],
    'checksums-archives-calibrated': ['archives-calibrated'],
    'checksums-archives-diagrams'  : ['archives-diagrams'],
    'checksums-archives-metadata'  : ['archives-metadata'],
    'checksums-archives-previews'  : ['archives-previews'],

    'checksums-volumes'   : ['volumes'],
    'checksums-calibrated': ['calibrated'],
    'checksums-diagrams'  : ['diagrams'],
    'checksums-metadata'  : ['metadata'],
    'checksums-previews'  : ['previews'],

    'archives-volumes'    : ['volumes'],
    'archives-calibrated' : ['calibrated'],
    'archives-diagrams'   : ['diagrams'],
    'archives-metadata'   : ['metadata'],
    'archives-previews'   : ['previews'],

    'volumes'   : ['volumes', 'calibrated', 'diagrams', 'metadata', 'previews'],
    'calibrated': ['calibrated', 'volumes', 'diagrams', 'metadata', 'previews'],
    'diagrams'  : ['diagrams', 'previews', 'volumes', 'calibrated', 'metadata'],
    'metadata'  : ['metadata', 'volumes', 'calibrated', 'diagrams', 'previews'],
    'previews'  : ['previews', 'diagrams', 'volumes', 'calibrated', 'metadata'],
    'documents' : ['volumes'],
}

VIEWABLE_EXTENSIONS = set([
    '.asc', '.c', '.cat', '.com', '.cpp', '.csh', '.csv', '.f', '.f77',
    '.fmt', '.for', '.gif', '.h', '.htm', '.html', '.idl', '.inc',
    '.jpeg_small', '.jpeg', '.jpg', '.lbl', '.pdf', '.pl', '.pm', '.png',
    '.pro', '.py', '.sh', '.tab', '.tif', '.tiff', '.txt',
])

PLAIN_TEXT_EXTENSIONS = set([
    '.asc', '.c', '.cat', '.com', '.cpp', '.csh', '.csv', '.f', '.f77',
    '.fmt', '.for', '.h', '.idl', '.inc', '.pl', '.pm', '.pro', '.py',
    '.sh', '.txt',
])

UNVIEWABLE_EXTENSIONS = set(['.zip', '.tar.gz', '.tar', '.tgz', '.jar'])

################################################################################
# Fill in HOLDINGS_PATHS, a list of absolute paths to the "holdings" directories
################################################################################

BOOT_TIME = psutil.boot_time()

# XXX WHY DO WE ALLOW A LIST OF HOLDINGS PATHS INSTEAD OF A SINGLE PATH?
def get_holdings_paths():
    """Return the list of holdings directories from the "PDS3_HOLDINGS_DIR" environment
    variable.

    Returns:
        list[str]: List containing the holdings directory path.

    Raises:
        OSError: If the PDS3_HOLDINGS_DIR environment variable is not set.
    """

    pds3_holdings_dir = os.getenv('PDS3_HOLDINGS_DIR')  # XXX PDS4
    if pds3_holdings_dir is not None:
        return [pds3_holdings_dir]
    else:
        raise OSError("'PDS3_HOLDINGS_DIR' environment variable not set")

# This code is preserved just in case we ever need it again. It searches for
# attached drives in the /Volumes directory that have names beginning with
# "pdsdata". We no longer use this approach.

def get_holdings_paths_old_way():
    """Return the list of holdings directories (deprecated method).

    This method searches for attached drives in /Volumes with names beginning
    with "pdsdata". This approach is no longer used.

    Returns:
        list[str]: List of holdings directory paths found.
    """

    # Read the volume info dict
    DISKNAME_REGEX = re.compile(r'^pdsdata[0-9]*(|-\w+)$')

    holdings_abspaths = []
    for volrootname in ('/Volumes', '/volumes'):
        for diskname in os.listdir(volrootname):
            match = DISKNAME_REGEX.match(diskname)
            if not match: continue

            holdings_abspaths.append(volrootname + '/' + diskname + '/holdings')

    return holdings_abspaths

def validate_holdings_paths(abspaths, logger):
    """Validate holdings directory paths and ensure required subdirectories exist.

    Parameters:
        abspaths (list[str]): List of absolute paths to validate.
        logger: Logger instance for logging warnings and errors.

    Returns:
        list[str]: List of valid holdings directory paths.

    Raises:
        OSError: If no valid holdings paths remain after validation.
    """

    valid_abspaths = []
    for abspath in abspaths:

        # If the system has just rebooted, wait for a possible remote mount.
        iter = 0
        while time.time() - BOOT_TIME < 120:
            parent = os.path.split(abspath)[0]
            if os.path.exists(parent) and 'holdings' in os.listdir(parent):
                break

            logger.warning('Holdings not found, pausing', abspath)
            time.sleep((os.getpid() + iter) % 5. + 0.9 * random.random())
            iter += 1

        abspath = abspath.rstrip('/')
        abspath = os.path.realpath(abspath)
        abspath = os.path.abspath(abspath)

        if not os.path.exists(abspath):
            logger.fatal('Holdings not found', abspath)

        if not abspath.endswith('/holdings'):
            logger.error('Not a holdings directory, ignored', abspath)
            continue

        prefix_ = abspath[:-len('holdings')]
        for dirname in ('holdings', 'shelves', 'volinfo'):
            testpath = prefix_ + dirname

            if not os.path.exists(testpath):
                logger.warning('Directory is missing, ignored', testpath)
                continue

            if not os.path.isdir(testpath):
                logger.error('Not a directory, ignored', testpath)
                continue

        valid_abspaths.append(abspath)

    if not valid_abspaths:
        raise OSError('Holdings list is empty')

    return valid_abspaths


################################################################################
################################################################################
# Begin executable code...
################################################################################
# Set up Viewmaster page cache
################################################################################

def get_holdings_path(logger):
    """Get and validate the holdings path from environment variable.

    Parameters:
        logger: Logger instance for logging errors.

    Returns:
        list[str]: List containing a single validated holdings directory path.

    Raises:
        SystemExit: If the holdings path cannot be retrieved or validated.
    """

    global HOLDINGS_PATHS

    try:
        paths = get_holdings_paths()
        paths = validate_holdings_paths(paths, logger)
    except Exception:
        logger.exception('Failed to get or validate holdings path')
        sys.exit(1)

    if len(paths) != 1:
        raise RuntimeError(f'Expected exactly one holdings path, got {len(paths)}')
    HOLDINGS_PATHS = paths

    return HOLDINGS_PATHS


def get_page_cache(logger):
    """Initialize and return the page cache instance.

    Sets up either a MemcachedCache or DictionaryCache based on configuration.
    Falls back to DictionaryCache if Memcache connection fails.

    Parameters:
        logger: Logger instance for logging cache setup information.

    Returns:
        pdscache.Cache|None: Cache instance if PAGE_CACHING is enabled,
            otherwise None.
    """

    global PAGE_CACHE

    page_cache = None
    # Set up the page cache if requested
    if PAGE_CACHING:
        memcache_port = VIEWMASTER_MEMCACHE_PORT
        if memcache_port:
            try:
                logger.info('Connecting Viewmaster to Memcache [%s]' %
                            memcache_port)
                page_cache = pdscache.MemcachedCache(memcache_port,
                                                    lifetime=pdsfile.cache_lifetime,
                                                    logger=logger)

            # On failure, switch to DictionaryCache
            except pylibmc.Error:
                logger.warning('Failed to connect Viewmaster to Memcache [%s]' %
                               memcache_port)
                memcache_port = None

        if not memcache_port:
            page_cache = pdscache.DictionaryCache(lifetime=pdsfile.cache_lifetime,
                                                limit=10000, logger=logger)
            logger.info('Using DictionaryCache for page caching')

    else:
        logger.info('Page caching OFF')

    if PAGE_CACHE is None:
        PAGE_CACHE = page_cache

    return PAGE_CACHE


################################################################################
# Function to reset the caches; should work when multiple threads all share a
# common MemCache.
################################################################################

def initialize_caches(reset=False):
    """Initialize the caches.

    This preloads `Pds3File` holdings, prepares `Pds3File` caches and optionally clears
    the page cache when it differs from the PdsFile cache backend.

    Parameters:
        reset (bool): If True, clears caches before initializing.

    Returns:
        None
    """

    global LOGGER, HOLDINGS_PATHS, PAGE_CACHE

    LOGGER.replace_root(HOLDINGS_PATHS)
    print(VIEWMASTER_PREFIX_+ICON_URL_)
    Pds3File.preload(HOLDINGS_PATHS, port=PDSFILE_MEMCACHE_PORT,
                     clear=reset, icon_url=ICON_URL_)

    if reset and PAGE_CACHE and (PDSFILE_MEMCACHE_PORT !=
                                 VIEWMASTER_MEMCACHE_PORT):
        PAGE_CACHE.clear()


################################################################################
################################################################################
################################################################################

def load_infopage_content(page_pdsfile, hrefs=True):
    """Load and optionally linkify a text info page.

    Reads a PDS3 text-like file, sanitizes for HTML, and inserts hyperlinks to
    recognized file references found via `internal_link_info` metadata.

    Parameters:
        page_pdsfile (Pds3File): PdsFile instance representing the info page.
        hrefs (bool): If True, insert anchor tags for recognized filenames.

    Returns:
        str: HTML-safe content with optional links; empty string on I/O error.
    """

    # Sorts tuples by increasing recno, then decreasing length
    def sort_key(tup):
        return (tup[0], -len(tup[1]))

    # Load the file
    try:
        with open(page_pdsfile.abspath, 'r') as f:
            lines = f.readlines()
    except OSError:
        return ''

    # Strip carriage control and trailing whitespace
    lines = [line.rstrip().replace('<', '&lt;').replace('>', '&gt;')
             for line in lines]

    # Replace non-ASCII characters that would break HTML
    for k in range(len(lines)):
        line = lines[k]
        cleaned = ''.join(c if ord(c) < 128 else ' ' for c in line)
        lines[k] = cleaned

    # If skipping HREF insertion, we're done
    if not hrefs:
        return '\n'.join(lines)

    # Retrieve the link info
    link_info = page_pdsfile.internal_link_info
    if not link_info:
        return '\n'.join(lines)

    # Remove duplicates (filename appears more than once in same line)
    link_info = list(set(link_info))

    # Sort from longer to shorter basenames when tuples have the same recno
    # This prevents 'ref.cat' from overriding 'projref.cat' in the same line
    link_info.sort(key=sort_key)

    # Insert hrefs (carefully!)
    for (recno, basename, abspath) in link_info:
        pdsf = Pds3File.from_abspath(abspath)
        line = lines[recno]
        parts = line.split(basename)

        # Deal with case of 'projref.cat' and 'ref.cat' in the same record
        new_parts = []
        k = 0
        while k < len(parts):
            part = parts[k]
            if '<a href' in part and '</a>' not in part:
                new_parts.append(basename.join(parts[k:k+3]))
                k += 3
            else:
                new_parts.append(part)
                k += 1

        ext = os.path.splitext(abspath)[1].lower()
        if ext in VIEWABLE_EXTENSIONS:
            href = (f'<a href="{LOCALHOST}{pdsf.url}" target="_blank">' +
                    f'<span class="tip">{basename}<span class="tiptext" ' +
                    'style="font-family: arial;">' +
                    'View this file</span></span></a>')
        else:
            href = (f'<a href="{VIEWMASTER_PREFIX_}{pdsf.logical_path}">' +
                    f'<span class="tip">{basename}<span class="tiptext" ' +
                    'style="font-family: arial;">' +
                    'View this file in Viewmaster</span></span></a>')
        lines[recno] = href.join(new_parts)

    # Insert name tags
    values = set()
    for k in range(len(lines)):
        line = lines[k]
        parts = line.partition('=')
        if not parts[1]: continue

        keyword = parts[0].strip()
        value = parts[2].strip()

        if keyword == 'OBJECT':
            recno = k
            continue

        if recno and keyword == 'NAME' and value not in values:
            lines[recno] = ('<a name="%s"></a>' % value) + lines[recno]
            values.add(value)
            recno = 0

    return '\n'.join(lines)

################################################################################

def get_prev_next_navigation(query_pdsfile, logger):
    """Compute neighbors for navigation before and after a target file/dir.

    The target file/dir itself is included as the first element in each list. List sizes
    and text lengths are constrained by `MAX_NAV_COUNT` and `MAX_NAV_STRLEN`.

    Parameters:
        query_pdsfile (Pds3File): PdsFile instance (a file or directory) around which to
            build navigation.
        logger: Logger instance for logging operations.

    Returns:
        tuple[list[Pds3File], list[Pds3File]]: Two lists `(prev, next)` where
        each entry is a copy enriched with `nav_name`, `division`, and
        `terminated` attributes used for display.
    """

    query_copy = query_pdsfile.copy()
    query_copy.nav_name = query_copy.basename
    query_copy.division = False
    query_copy.terminated = False     # default, might be changed

    # Define iterator for directories or files
    try:
        if query_pdsfile.isdir:
            forward = pdsiterator.PdsDirIterator(query_pdsfile, logger=logger)
            backward = forward.copy(-1)

        # Index rows
        elif query_pdsfile.is_index_row:
            forward = pdsiterator.PdsRowIterator(query_pdsfile, logger=logger)
            backward = forward.copy(-1)

        # Files using split rules
        else:
            pattern = query_pdsfile.SIBLINGS.first(query_pdsfile.logical_path)
            if not pattern:
                parts = query_pdsfile.split
                pattern = '*' + parts[1] + parts[2]

            forward = pdsiterator.PdsFileIterator(query_pdsfile,
                                                  pattern=pattern,
                                                  logger=logger)
            backward = forward.copy(-1)

    # On failure, this is a virtual directory
    except (ValueError, AttributeError) as e:
        return ([query_copy], [query_copy])

    # Iterate to get neighbors before and after
    # pages['next'] is forward navigation; pages['prev] is backward navigation
    # Both lists start with this item
    page = {}
    try:
        tuples = [(forward, 'next'), (backward, 'prev')]

        for (iter, name) in tuples:
            neighbors = [query_copy.copy()]         # neighbors[0] is self

            next_strlen = len(query_pdsfile.basename) // 2  # count name once
            next_count = 0

            iteration_terminated = True
            for (neighbor, nav_name, level) in iter:
                neighbor = Pds3File.from_logical_path(neighbor)
                neighbor.nav_name = nav_name
                neighbor.division = (level > 0)
                neighbor.terminated = False     # default

                # Track the string length and item count
                next_count += 1
                next_strlen += len(nav_name) + NAV_SPACING

                # Always append at least one
                # Append up to limit or if there is room
                if next_count <= 1 or (next_count <= MAX_NAV_COUNT and
                                       next_strlen <= MAX_NAV_STRLEN):
                    neighbors.append(neighbor)
                    if neighbor.division:
                        next_strlen += NAV_DIVISION_STRLEN

                # Break once we have established whether the list terminates
                else:
                    iteration_terminated = False
                    break

            neighbors[-1].terminated = iteration_terminated
            page[name] = neighbors

    # Otherwise, a virtual directory
    except (ValueError, AttributeError) as e:
        return ([query_copy], [query_copy])

    # Deal with a nonexistent index row--it still has neighbors!
    if query_pdsfile.is_index_row and not query_pdsfile.exists:

        # Note that, in this case, each list begins with query_pdsfile, but
        # that row_pdsfile is missing from both lists. We need to put it back
        # in the proper place

        row_pdsfile = row_pdsfile.copy()
        row_pdsfile.nav_name = row_pdsfile.basename
        row_pdsfile.division = False
        row_pdsfile.terminated = False

        nearest_index = query_pdsfile.find_row_number_at_or_below()
        if nearest_index < 0:   # row_pdsfile comes after
            page['next'] = page['next'][:1] + [row_pdsfile] + page['next'][1:]

        else:                   # row_pdsfile goes before
            page['prev'] = page['prev'][:1] + [row_pdsfile] + page['prev'][1:]

    return (page['prev'], page['next'])

################################################################################

def list_next_pdsfiles(query_pdsfile):
    """List up to `MAX_PAGES` forward neighbors from a starting target file/dir.

    Parameters:
        query_pdsfile (Pds3File): Starting file or directory.

    Returns:
        list[Pds3File]: Starting target file or directory followed by forward neighbors.
    """

    siblings = [query_pdsfile]

    if query_pdsfile.isdir:
        forward = pdsiterator.PdsDirIterator(query_pdsfile)
        for (logical_path, _, _) in forward:
            siblings.append(Pds3File.from_logical_path(logical_path))
            if len(siblings) >= MAX_PAGES:
                break

    else:
        forward = pdsiterator.PdsFileIterator(query_pdsfile)
        for (logical_path, _, _) in forward:
            siblings.append(Pds3File.from_logical_path(logical_path))
            if len(siblings) >= MAX_PAGES:
                break

    return siblings

################################################################################

def fill_level_navigation_links(page, params):
    """Populate `nav_link` for level navigation hierarchy items.

    Parameters:
        page (dict): Page dictionary being assembled.
        params (dict): Current query parameters.

    Returns:
        None
    """

    # Fill in level navigation links for all tables
    level_params = params.copy()
    level_params['skip'] = ''
    level_params['rows'] = ''
    level_params['selection'] = ''
    level_link_suffix_w_filter = url_params(level_params)

    level_params['filter'] = ''
    level_link_suffix_wo_filter = url_params(level_params)

    for table in page['tables'] + page['associations'] + page['documents']:
        levels = table.levels
        for k in range(len(levels)):
            level = levels[k]
            if level.logical_path == page['query'].logical_path:
                level.nav_link = ''
            elif k == 0:
                nav_link = VIEWMASTER_PREFIX_ + level.logical_path
                level.nav_link = nav_link + level_link_suffix_w_filter
            else:
                nav_link = VIEWMASTER_PREFIX_ + level.logical_path
                level.nav_link = nav_link + level_link_suffix_wo_filter

################################################################################

def fill_prev_next_navigation_links(page, params):
    """Populate `nav_link` for neighbor navigation lists.

    Parameters:
        page (dict): Page dictionary with `prev` and `next` lists.
        params (dict): Current query parameters.

    Returns:
        None
    """

    nav_params = params.copy()
    nav_params['skip'] = ''
    nav_params['rows'] = ''
    nav_params['selection'] = ''
    nav_link_suffix = url_params(nav_params)

    for nav in page['next'] + page['prev']:
        if nav.logical_path == page['query'].logical_path:
            nav.nav_link = ''
        else:
            nav.nav_link = VIEWMASTER_PREFIX_ + nav.logical_path + \
                                                nav_link_suffix

################################################################################

def fill_table_navigation_links(page, params):
    """Populate `webapp_link` for rows across page tables.

    Parameters:
        page (dict): Page dictionary with `tables`, `associations`, `documents`.
        params (dict): Current query parameters.

    Returns:
        None
    """

    group_params = params.copy()
    group_params['skip'] = ''
    group_params['rows'] = ''
    group_params['selection'] = ''
    group_suffix = url_params(group_params)

    for table in page['tables']:
        for group in table.iterator():
          if len(group):
            group.webapp_link = VIEWMASTER_PREFIX_ + \
                                group.rows[0].logical_path + group_suffix

            for row in group.rows:
                row.webapp_link = VIEWMASTER_PREFIX_ + row.logical_path + \
                                                        group_suffix

    group_params['filter'] = ''
    group_params['pages'] = 1
    group_suffix = url_params(group_params)

    for table in page['associations'] + page['documents']:
        for group in table.iterator():
          if len(group):
            group.webapp_link = VIEWMASTER_PREFIX_ + \
                                group.rows[0].logical_path + group_suffix

            for pdsf in group.iterator():
                pdsf.webapp_link = VIEWMASTER_PREFIX_ + pdsf.logical_path + \
                                                        group_suffix

################################################################################

def get_parallels(query_pdsfile):
    """Find parallel files/dirs in other trees and versions for a target file/dir.

    Parameters:
        query_pdsfile (Pds3File): The target file or directory.

    Returns:
        dict[str, Pds3File|None]: Mapping of category/version keys to parallels,
        including `previous`, `next`, `latest`, and version ranks.
    """

    parallels = {}
    for voltype in pdsfile.Pds3File.VOLTYPES:
        if voltype == 'bundles':  # XXX PDS4
            continue
        for archives in ('archives-', ''):
            key = archives + voltype
            parallels[key] = query_pdsfile.associated_parallel(category=key)

        # When the association is a single directory, use that instead
        test_pdsfiles = query_pdsfile.associated_pdsfiles(voltype)
        if len(test_pdsfiles) == 1 and test_pdsfiles[0].isdir:
            parallels[voltype] = test_pdsfiles[0]

    for key in ['latest', 'previous', 'next']:
        parallel = query_pdsfile.associated_parallel(rank=key)
        parallels[key] = parallel

    if (parallels['previous'] and
        parallels['previous'].abspath == query_pdsfile.abspath):
            parallels['previous'] = None

    if (parallels['next'] and
        parallels['next'].abspath == query_pdsfile.abspath):
            parallels['next'] = None

    for key in query_pdsfile.version_ranks:
        parallels[key] = query_pdsfile.associated_parallel(rank=key)

    # Handle index row suffixes
    if query_pdsfile.is_index_row:
        for key in ['metadata', 'latest', 'previous', 'next']:
            if not parallels[key]: continue

            if parallels[key].basename.lower().endswith('.tab'):
                parallels[key] = parallels[key].child(query_pdsfile.basename,
                                                      must_exist=False)

        # Let 'volumes' point to the associated data file
        data_pdsfile = query_pdsfile.data_pdsfile_for_index_row()
        if data_pdsfile:
            if data_pdsfile.islabel:
                abspaths = data_pdsfile.data_abspaths
                if len(abspaths):
                    parallels['volumes'] = Pds3File.from_abspath(abspaths[0])
            else:
                parallels['volumes'] = data_pdsfile

    return parallels

################################################################################

SAFE_FILTER_REGEX = re.compile(r'^\w+\*(|\.*)$', re.I)
SAFE_FILTER_CATEGORIES = ('volumes', 'previews', 'diagrams', 'calibrated')

def fill_parallels_navigation_links(page, params):
    """Populate `webapp_link` for files/dirs in the `parallels` map.

    Includes the filter when safe for same-depth categories.

    Parameters:
        page (dict): Page dictionary with `parallels`.
        params (dict): Current query parameters.

    Returns:
        None
    """

    temp_params = params.copy()
    temp_params['skip'] = ''
    temp_params['rows'] = ''
    temp_params['selection'] = ''
    suffix_w_filter = url_params(temp_params)

    temp_params['filter'] = ''
    suffix_wo_filter = url_params(temp_params)

    # Proceed assuming filter is unsafe
    for pdsf in page['parallels'].values():
        if pdsf:
            pdsf.webapp_link = VIEWMASTER_PREFIX_ + pdsf.logical_path + \
                                                    suffix_wo_filter

    # Restore the filter where safe
    query_pdsfile = page['query']
    is_safe = SAFE_FILTER_REGEX.match(params['filter']) is not None and \
              query_pdsfile.category_[:-1] in SAFE_FILTER_CATEGORIES and \
              query_pdsfile.interior != ''

    if is_safe:
        lparts = len(query_pdsfile.logical_path.split('/'))
        for key in SAFE_FILTER_CATEGORIES:
            pdsf = page['parallels'][key]
            if pdsf and len(pdsf.logical_path.split('/')) == lparts:
                pdsf.webapp_link = VIEWMASTER_PREFIX_ + pdsf.logical_path +\
                                                        suffix_w_filter

################################################################################

def fill_option_links(page, params):
    """Define URLs for display options (grid, multipage, continuous).

    Parameters:
        page (dict): Page dictionary to annotate.
        params (dict): Current query parameters.

    Returns:
        None
    """

    # Create URLs for all alternative options...
    query_pdsfile = page['query']
    base_webapp_link = VIEWMASTER_PREFIX_ + query_pdsfile.logical_path

    page['grid_view_allowed'] = query_pdsfile.grid_view_allowed
    page['multipage_view_allowed'] = query_pdsfile.multipage_view_allowed
    page['continuous_view_allowed'] = query_pdsfile.continuous_view_allowed

    # Options to change the number of pages
    links_for_page_counts = (MAX_PAGES + 1) * ['']
    if query_pdsfile.multipage_view_allowed:
        for p in range(1, page['available_page_count']+1):
            if p == params['pages']:
                links_for_page_counts[p] = ''
            else:
                temp = params.copy()
                temp['pages'] = p
                links_for_page_counts[p] = base_webapp_link + url_params(temp)

    page['links_for_page_counts'] = links_for_page_counts

    # Options for list vs. small grid vs. large grid
    links_for_grid_display = 3 * ['']
    if query_pdsfile.grid_view_allowed:
        for g in range(3):
            if g == params['grid']:
                links_for_grid_display[g] = ''
            else:
                temp = params.copy()
                temp['grid'] = g
                links_for_grid_display[g] = base_webapp_link + url_params(temp)

    page['links_for_grid_display'] = links_for_grid_display

    # Continuous
    links_for_continuous = 2 * ['']
    if query_pdsfile.continuous_view_allowed:
        for c in range(2):
            if c == params['continuous']:
                links_for_continuous[c] = ''
            else:
                temp = params.copy()
                temp['continuous'] = c
                links_for_continuous[c] = base_webapp_link + url_params(temp)

    page['links_for_continuous'] = links_for_continuous

################################################################################
################################################################################
################################################################################

def get_directory_page(query_pdsfile, logger):
    """Assemble the `page` dictionary for a directory view.

    The dictionary includes various info for rendering the target dir.

    Parameters:
        query_pdsfile (Pds3File): Directory to display.
        logger: Logger instance for logging operations.

    Returns:
        dict: Page dictionary with groups, associations, documents, navigation,
        and info content for rendering.
    """

    page = {}
    page['query'] = query_pdsfile
    page['grid_view_allowed'] = query_pdsfile.grid_view_allowed

    # Load and group the children. This is a list of PdsGroup objects.
    pdsgroups = PdsGroup.group_children(query_pdsfile)

    # Get local navigation
    (page['prev'], page['next']) = get_prev_next_navigation(query_pdsfile, logger)
    parallels = get_parallels(query_pdsfile)
    page['parallels'] = parallels

    # Save an ordered list of PdsGroupTable objects
    table1 = PdsGroupTable(pdsgroups, parent=query_pdsfile)
    page['tables'] = [table1]

    # Create a list of excluded pdsfiles. This is a list of the logical paths
    # of files that already appear elsewhere on the page, and therefore do not
    # need to be repeated as associated files.
    exclusions = set([query_pdsfile.logical_path]
                + query_pdsfile.logicals_for_basenames(query_pdsfile.childnames)
                + list(table1.pdsfile_iterator())
                + table1.levels
                + [parallels[k].logical_path for k in parallels
                        if isinstance(k,int) and parallels[k]])

    # Create tables for associated categories
    associations = []
    if not query_pdsfile.is_category_dir:   # skip category-level associations
      for category in ASSOCIATED_CATEGORIES[query_pdsfile.category_[:-1]]:
        pdsfiles = query_pdsfile.associated_pdsfiles(category)
        if pdsfiles:
            associations += PdsGroupTable.tables_from_pdsfiles(pdsfiles,
                                                               exclusions)
            exclusions |= set(Pds3File.logicals_for_pdsfiles(pdsfiles))

    page['associations'] = associations

    pdsfiles = query_pdsfile.associated_pdsfiles('documents')
    documents = PdsGroupTable.tables_from_pdsfiles(pdsfiles, exclusions)
    page['documents'] = documents

    # Find the info file if any
    page['info'] = None
    page['info_content'] = None
    if query_pdsfile.info_basename:
        for group in pdsgroups:
            for pdsf in group.rows:
                if pdsf.basename == query_pdsfile.info_basename:
                    page['info'] = pdsf
                    page['info_content'] = load_infopage_content(pdsf)
                    break       # stop on first match

        if not page['info']:
            for table in page['associations']:
                for group in table.groups:
                    for pdsf in group.rows:
                        if pdsf.basename == query_pdsfile.info_basename:
                            page['info'] = pdsf
                            page['info_content'] = load_infopage_content(pdsf)
                            break

    return page

################################################################################

def directory_page_html(query_pdsfile, params, logger):
    """Render a directory view to HTML.

    Parameters:
        query_pdsfile (Pds3File): Directory to display.
        params (dict): Cleaned query parameters.
        logger: Logger instance for logging operations.

    Returns:
        str|tuple: HTML string or a tuple `('REDIRECT_NEEDED', new_path)`.
    """

    page = get_directory_page(query_pdsfile, logger)

    page['params'] = params
    page['localhost'] = LOCALHOST
    page['viewmaster_'] = VIEWMASTER_PREFIX_
    page['set_filter'] = SET_FILTER
    page['home'] = WEBSITE_HTTP_HOME
    page['pds'] = PDS
    page['viewable_extensions'] = VIEWABLE_EXTENSIONS
    page['unviewable_extensions'] = UNVIEWABLE_EXTENSIONS

    if query_pdsfile.is_merged:
        page['wget_path'] = None
    else:
        page['wget_path'] = (query_pdsfile.html_root_ +
                             query_pdsfile.logical_path)

    # Handle a selection (currently not implemented)
    if params['selection']:
        anchor_suffix = '#' + html.escape(params['selection'], quote=True)
    else:
        anchor_suffix = ''

    # Determine how many pages are available
    target_page_count = params['pages']
    if query_pdsfile.multipage_view_allowed:
        all_pdsfiles = list_next_pdsfiles(query_pdsfile)
    else:
        all_pdsfiles = [query_pdsfile]

    available_page_count = len(all_pdsfiles)
    actual_page_count = min(target_page_count, available_page_count)

    page['available_page_count'] = available_page_count
    page['page_count'] = actual_page_count
    page['max_pages'] = MAX_PAGES

    all_pdsfiles = all_pdsfiles[:actual_page_count]
    page['page_pdsfiles'] = all_pdsfiles

    # Generate additional pages, merge tables
    if actual_page_count > 1:

        # Merge tables
        table1 = page['tables'][0]
        tables = [table1]

        for pdsf in all_pdsfiles[1:]:
            next_page = get_directory_page(pdsf, logger)
            next_table = next_page['tables'][0]
            tables += [next_table]

        page['tables'] = tables

    # Filter the tables if necessary
    filter_regex = params['filter_regex']
    if filter_regex:
        filtered_tables = []
        group_count = 0
        for table in page['tables']:
            table.filter(filter_regex)
            group_count += len(table.iterator())

            cleaned = table.remove_hidden()
            filtered_tables.append(table.remove_hidden())

        page['tables'] = filtered_tables

        # Report absence of matches
        if group_count == 0:
            flash('No files match expression: <font face="Courier">' +
                  params['filter'] + '</font>')

    # Finalize the skip and row count
    tables = page['tables']
    total_rows = sum([len(t) for t in tables])
    rows = min(max(MIN_ROWS, params['rows']), MAX_ROWS)
    skip = max(0, min(params['skip'], total_rows - rows))
    if (skip,rows) != (params['skip'],params['rows']):
        params['rows'] = rows
        params['skip'] = skip
        new_query_path = query_pdsfile.logical_path + url_params(params)

        # Inside the viewmaster() function, this response will trigger the
        # necessary redirect
        return ('REDIRECT_NEEDED', new_query_path)

    # Links for additional row ranges in the table. These are:
    # (url for first rows, url for rows before these, url for rows after these,
    #  url for last rows)
    if skip == 0 and rows >= total_rows:
        row_range_links = None
    else:
        temp_params = params.copy()
        if skip == 0:
            link1 = None
            link2 = None
        else:
            temp_params['skip'] = 0
            link1 = (VIEWMASTER_PREFIX_ + query_pdsfile.logical_path +
                     url_params(temp_params))

            temp_params['skip'] = max(0, skip - rows)
            link2 = (VIEWMASTER_PREFIX_ + query_pdsfile.logical_path +
                     url_params(temp_params))

        if skip + rows >= total_rows:
            link3 = None
            link4 = None
        else:
            temp_params['skip'] = min(skip + rows, total_rows - rows)
            link3 = (VIEWMASTER_PREFIX_ + query_pdsfile.logical_path +
                     url_params(temp_params))

            temp_params['skip'] = total_rows - rows
            link4 = (VIEWMASTER_PREFIX_ + query_pdsfile.logical_path +
                     url_params(temp_params))

        row_range_links = (link1, link2, link3, link4)

    page['row_range_links'] = row_range_links
    page['total_rows'] = total_rows

    # Identify the visible tables and row ranges
    global_row0 = skip
    global_row1 = min(skip + rows, total_rows)

    table_is_visible = []       # True if this table will be visible
    table_row0 = []             # First visible row in this table, if visible
    table_row1 = []             # One more than last visible row in this table
    for table in tables:
        ltable = len(table)
        if global_row0 >= ltable:
            is_visible = False
            row0 = 0
            row1 = 0
        elif global_row0 >= 0:
            is_visible = True
            row0 = global_row0
            row1 = min(global_row1, ltable)
        elif global_row1 > 0:
            is_visible = True
            row0 = 0
            row1 = min(global_row1, ltable)
        else:
            is_visible = False
            row0 = 0
            row1 = 0

        table_row0.append(row0)
        table_row1.append(row1)
        table_is_visible.append(is_visible)

        global_row0 -= ltable
        global_row1 -= ltable

    # If necessary, reconstruct the associations with a new set of exclusions
    if filter_regex or actual_page_count > 1:

        # Assemble all the exclusions
        exclusions = []
        for table in page['tables']:
            exclusions += list(table.pdsfile_iterator()) + table.levels

        exclusions = set(Pds3File.logicals_for_pdsfiles(exclusions))

        # Create tables for associated categories
        associations = []
        for category in ASSOCIATED_CATEGORIES[query_pdsfile.category_[:-1]]:
            pdsfiles = []
            for pdsf in all_pdsfiles:
                pdsfiles += pdsf.associated_pdsfiles(category)
            associations += PdsGroupTable.tables_from_pdsfiles(pdsfiles,
                                                               exclusions)
        page['associations'] = associations

    # Append row and table visibility info for the associations and documents
    for table in page['associations'] + page['documents']:
        table_row0.append(0)
        table_row1.append(len(table))
        table_is_visible.append(True)

    page['table_row0'] = table_row0
    page['table_row1'] = table_row1
    page['table_is_visible'] = table_is_visible

    # Fill navigation links
    fill_level_navigation_links(page, params)
    fill_prev_next_navigation_links(page, params)
    fill_table_navigation_links(page, params)
    fill_parallels_navigation_links(page, params)
    fill_option_links(page, params)

    # Define filter form
    form = FilterForm()
    form.hidden.data = request.url
    form.filter.data = params['filter']

    grid_layout = page['params']['grid'] and page['grid_view_allowed']
    page['grid_layout'] = grid_layout

    template = 'grid_view.html' if grid_layout else 'table_view.html'
    return render_template(template, filter_form=form, **page)

################################################################################
################################################################################
################################################################################

def get_product_page_info(query_pdsfile, logger):
    """Assemble the `page` dictionary for a product view.

    The dictionary includes various info for rendering the target file.

    Parameters:
        query_pdsfile (Pds3File): File (or index row) to display.
        logger: Logger instance for logging operations.

    Returns:
        dict: Page dictionary ready for rendering a product.
    """

    page = {}
    page['query'] = query_pdsfile

    # For an index row, find siblings of the parent, which is the index table;
    # otherwise, find siblings of the query object
    if query_pdsfile.is_index_row:
        sib_pdsfile = query_pdsfile.parent()
    else:
        sib_pdsfile = query_pdsfile

    # Find siblings (same anchor, same parent)
    query_parent = sib_pdsfile.parent()
    sibnames = query_parent.childnames_by_anchor(sib_pdsfile.anchor)

    # Include the label of a target
    label_basename = sib_pdsfile.label_basename
    if label_basename and label_basename not in sibnames:
        sibnames.append(label_basename)

    # Include targets of a label
    for abspath in sib_pdsfile.data_abspaths:
        basename = os.path.basename(abspath)
        if basename not in sibnames:
            sibnames.append(basename)

    # Convert to PdsFiles
    siblings = query_parent.pdsfiles_for_basenames(sibnames)

    # Choose the info file
    info_pdsfile = None
    if label_basename:
        info_pdsfile = query_parent.child(label_basename)
    elif query_pdsfile.extension.lower() in ('.cat', '.txt', '.fmt'):
        info_pdsfile = query_pdsfile
    elif query_pdsfile.is_index_row:            # index row case
        parent_label_abspath = sib_pdsfile.label_abspath
        info_pdsfile = Pds3File.from_abspath(parent_label_abspath)
    elif query_pdsfile.islabel:                 # show self
        info_pdsfile = query_pdsfile
    else:                                       # show label if any
        labels = [sib for sib in siblings if sib.is_label]
        if len(labels) == 0:                    # if no label...
            if query_pdsfile.extension.lower() in PLAIN_TEXT_EXTENSIONS:
                info_pdsfile = query_pdsfile    # ...show content if text
            else:
                info_pdsfile = None
        elif len(labels) == 1:                  # if one label, show it
            info_pdsfile = labels[0]
        else:                                   # if more than one, find best
            (anchor, suffix, ext) = query_pdsfile.split()
            patterns = (anchor + suffix + '.',
                        anchor + suffix,
                        anchor + '.',
                        anchor)
            usable_info_pdsfile = labels[0]
            for pattern in patterns:
                query_labels = [sib for sib in labels
                                if sib.basename.startswith(pattern)]
                if len(query_labels) == 1:
                    info_pdsfile = query_labels[0]
                    break
                elif len(query_labels) > 1:
                    usable_info_pdsfile = query_labels[0]

            if info_pdsfile is None:
                info_pdsfile = usable_info_pdsfile

    if info_pdsfile:
        page['info'] = info_pdsfile
        page['info_content'] = load_infopage_content(info_pdsfile)
    else:
        page['info'] = None
        page['info_content'] = None

    # Get neighbor navigation and warn about timing if it is very slow
    start_time = datetime.datetime.now()
    (page['prev'], page['next']) = get_prev_next_navigation(query_pdsfile, logger)
    elapsed = (datetime.datetime.now() - start_time).total_seconds()
    if elapsed > 10:
        logger.warning('Neighbor navigation took %.1f sec' % elapsed,
                       query_pdsfile.abspath)

    parallels = get_parallels(query_pdsfile)
    page['parallels'] = parallels

    # Begin an ordered list of PdsGroupTable objects

    # Insert an index row object in front
    if query_pdsfile.is_index_row:
        table0 = PdsGroupTable()
        table0.insert_group(PdsGroup(query_pdsfile))
        tables = [table0]
        merge_sibs = True
    else:
        tables = []
        merge_sibs = False

    # The next table contains the object and its siblings
    table1 = PdsGroupTable()
    siblings = sib_pdsfile.sort_siblings(siblings)
    for pdsf in siblings:
        table1.insert_group(PdsGroup(pdsf), merge=merge_sibs)

    tables.append(table1)
    page['tables'] = tables

    # Create a list of excluded pdsfiles. This is a list of abspaths that
    # already appear in the page, and therefore do not need to be repeated as
    # "Related files".
    exclusions = set(list(table1.pdsfile_iterator()) + table1.levels
                  + [parallels[k] for k in parallels if isinstance(k,int)
                                                        and parallels[k]])

    # Tabulate associated files
    associations = []
    for sibling in siblings:
        if sibling.islabel:
            abspaths = sibling.linked_abspaths
            abspaths = [p for p in abspaths if p.lower().endswith('.fmt')]
            associations += PdsGroupTable.tables_from_pdsfiles(abspaths,
                                                               exclusions)
            exclusions |= set(abspaths)

    # Insert associated categories
    for category in ASSOCIATED_CATEGORIES[query_pdsfile.category_[:-1]]:
        pdsfiles = query_pdsfile.associated_pdsfiles(category)
        associations +=  PdsGroupTable.tables_from_pdsfiles(pdsfiles,
                                                            exclusions)
        exclusions |= set(Pds3File.logicals_for_pdsfiles(pdsfiles))

    page['associations'] = associations

    # Insert documents
    if query_pdsfile.is_index_row:
        pdsfiles = []
    else:
        pdsfiles = query_pdsfile.associated_pdsfiles('documents')
    documents = PdsGroupTable.tables_from_pdsfiles(pdsfiles, exclusions)
    page['documents'] = documents

    # For an index row, include the data file in the main table
    data_pdsfile = query_pdsfile.data_pdsfile_for_index_row()
    if data_pdsfile:
        group = PdsGroup(data_pdsfile)
        data_parent = data_pdsfile.parent()
        sibnames = data_parent.childnames_by_anchor(data_pdsfile.anchor)
        siblings = data_parent.pdsfiles_for_basenames(sibnames)
        for sibling in siblings:
            group.append(sibling)
        group.sort(labels_after=True)

        page['tables'].append(PdsGroupTable([group]))

    return page

################################################################################

def product_page_html(query_pdsfile, params, logger):
    """Render a product view to HTML.

    Parameters:
        query_pdsfile (Pds3File): Product to display.
        params (dict): Cleaned query parameters.
        logger: Logger instance for logging operations.

    Returns:
        str: Rendered HTML.
    """

    page = get_product_page_info(query_pdsfile, logger)

    page['params'] = params
    page['localhost'] = LOCALHOST
    page['viewmaster_'] = VIEWMASTER_PREFIX_
    page['home'] = WEBSITE_HTTP_HOME
    page['pds'] = PDS
    page['viewable_extensions'] = VIEWABLE_EXTENSIONS
    page['unviewable_extensions'] = UNVIEWABLE_EXTENSIONS

    parent = query_pdsfile.parent()
    if parent and not parent.is_merged:
        page['wget_path'] = query_pdsfile.html_root_ + parent.logical_path
    else:
        page['wget_path'] = None

    if params['preview'] in query_pdsfile.all_viewsets:
        page['selected_viewset'] = query_pdsfile.all_viewsets[params['preview']]
    else:
        page['selected_viewset'] = query_pdsfile.viewset

    # Determine how many pages are available
    target_page_count = params['pages']
    if query_pdsfile.multipage_view_allowed and not query_pdsfile.is_index_row:
        all_pdsfiles = list_next_pdsfiles(query_pdsfile)
    else:
        all_pdsfiles = [query_pdsfile]

    # Filter the pdsfiles if necessary
    filter_regex = params['filter_regex']
    if filter_regex:
        filtered_pdsfiles = []
        for pdsf in all_pdsfiles:
            match = filter_regex.match(pdsf.basename)
            if match:
                filtered_pdsfiles.append(pdsf)

        all_pdsfiles = filtered_pdsfiles

    available_page_count = len(all_pdsfiles)
    actual_page_count = min(target_page_count, available_page_count)

    page['available_page_count'] = available_page_count
    page['page_count'] = actual_page_count
    page['max_pages'] = MAX_PAGES

    all_pdsfiles = all_pdsfiles[:actual_page_count]
    page['page_pdsfiles'] = all_pdsfiles

    # Generate additional pages, merge tables
    if actual_page_count > 1:

        # Merge tables
        page['tables'] = PdsGroupTable.tables_from_pdsfiles(all_pdsfiles)

        # Reconstruct the associations with a new set of exclusions
        # Exclusions are logical paths that are not included as related products
        # at the bottom of the page, because they are already linked elsewhere
        # in the page.
        exclusions = []
        for table in page['tables']:
            exclusions += list(table.pdsfile_iterator()) + table.levels

        exclusions = set([f.logical_path for f in exclusions])

        # Create tables for associated categories
        associations = []
        for category in ASSOCIATED_CATEGORIES[query_pdsfile.category_[:-1]]:
            pdsfiles = []
            for pdsf in all_pdsfiles:
                pdsfiles += pdsf.associated_pdsfiles(category)
            associations += PdsGroupTable.tables_from_pdsfiles(pdsfiles,
                                                               exclusions)
        page['associations'] = associations

    # Merge index row tables in associations
    page['associations'] = \
                PdsGroupTable.merge_index_row_tables(page['associations'])

    # Fill in row ranges (which are used by directories, not products)
    table_is_visible = []
    table_row0 = []
    table_row1 = []
    for table in page['tables'] + page['associations'] + page['documents']:
        table_row0.append(0)
        table_row1.append(len(table))
        table_is_visible.append(True)

    page['table_row0'] = table_row0
    page['table_row1'] = table_row1
    page['table_is_visible'] = table_is_visible

    # Fill navigation links
    fill_level_navigation_links(page, params)
    fill_prev_next_navigation_links(page, params)
    fill_table_navigation_links(page, params)
    fill_parallels_navigation_links(page, params)
    fill_option_links(page, params)

    page['grid_layout'] = False

    # Handle special case of index row display
    if query_pdsfile.is_index_row:
        data_pdsfile = query_pdsfile.data_pdsfile_for_index_row()
        index_pdsfile = query_pdsfile.parent()

        # Pick a column to link to the data product's page
        filespec_column_name = None
        for column_name in pdstable.FILE_SPECIFICATION_COLUMN_NAMES:
            if column_name in index_pdsfile.column_names:
                filespec_column_name = column_name
                break

        # Generate the page sections
        maxlen = max([len(c) for c in index_pdsfile.column_names])
        sections = []

        if query_pdsfile.exists:
            for row_dict in query_pdsfile.row_dicts:
                section = []
                for column_name in index_pdsfile.column_names:
                    rec = ['<a href="#',
                           column_name,
                           '"><span class="tip">',
                           column_name.replace(' ', '&nbsp;'),
                           '<span class="tiptext" style="font-family:arial;">',
                           'Jump to this column definition in the label below',
                           '</span></span></a>',
                           (maxlen-len(column_name)) * '&nbsp;',
                           '&nbsp;=&nbsp;']
                    value = row_dict[column_name]
                    mask  = row_dict[column_name + '_mask']

                    if column_name == filespec_column_name and data_pdsfile:
                        value = ''.join([
                            '<a href="',
                            VIEWMASTER_PREFIX_,
                            data_pdsfile.logical_path,
                            '"><span class="tip">',
                            value.replace(' ', '&nbsp;'),
                            '<span class="tiptext" style="font-family:arial;">',
                            'View this file in Viewmaster',
                            '</span></span></a>'])

                    # Pad so that columns align in a monospaced font
                    rec += format_row_value(value, mask)
                    line = ''.join(rec)
                    section.append(line)

                sections.append(section)

        else:
            rec = ['<font color="red" face="sans-serif">',
                   'Sorry, no rows of table <a href="',
                   VIEWMASTER_PREFIX_,
                   index_pdsfile.logical_path,
                   '" style="color:FireBrick;font-weight:bold">',
                   index_pdsfile.basename,
                   '</a> are associated with product ']

            if data_pdsfile:
                rec += ['&ldquo;<a href="',
                        VIEWMASTER_PREFIX_,
                        data_pdsfile.logical_path,
                        '" style="color:FireBrick;font-weight:bold">',
                        data_pdsfile.basename,
                        '</a>&rdquo;.</font>']
            else:
                rec += ['&ldquo;', data_pdsfile.basename, '&rdquo;.</font>']

            section = [''.join(rec)]

            maxlen = max([len(c) for c in query_pdsfile.column_names])
            for column_name in index_pdsfile.column_names:
                rec = ['<font color="silver">',
                       column_name,
                       (maxlen-len(column_name)) * ' ',
                       ' = "N/A"</font>']

                # Pad so that columns align in a monospaced font
                line = ''.join(rec)
                line = line.replace(' ', '&nbsp;')
                line = line.replace('font&nbsp;', 'font ')
                section.append(line)

            sections = [section]

        page['sections'] = sections
        page['associations'] = []

        template = 'index_rows_view.html'
        return render_template(template, **page)

    # Otherwise, it's a normal product view
    else:
        template = 'table_view.html'
        return render_template(template, **page)

################################################################################

def format_row_value(value, mask, add_comment=True):
    """Format a single index-row value as a list of HTML string parts.

    Handles tuples, masked values, and strings. For masked values, the original
    value can be included as an HTML comment.

    Parameters:
        value (Any): The index-row value or tuple of values.
        mask (bool|sequence[bool]): Mask flag(s) for the value(s).
        add_comment (bool): Whether to include the unmasked value as a comment.

    Returns:
        list[str]: Parts to be concatenated into HTML-safe text.
    """

    # Handle a tuple of multiple values
    try:
        count = len(mask)
        reclist = format_tuple(value, mask)

        if sum(mask):
            reclist += ['    /* ']
            reclist += format_tuple(value, count*[False])
            reclist += [' */']

        return reclist

    except TypeError:
        pass

    # Handle a masked value
    if mask:
        if add_comment:
            reclist = ['NULL    /* ']
            reclist += format_row_value(value, False)
            reclist += [' */']
        else:
            reclist = ['NULL']

        return reclist

    # Handle a string
    if isinstance(value, str):
        return ['"', value, '"']

    # Handle anything else
    return [str(value)]

def format_tuple(values, masks):
    """Format a tuple of values with masks into HTML parts.

    Parameters:
        values (sequence): Values to format.
        masks (sequence[bool]): Mask flags for each value.

    Returns:
        list[str]: Parts to be concatenated into HTML-safe text.
    """

    reclist = ['(']
    for (v,m) in zip(values, masks):
        reclist += format_row_value(v, m, add_comment=False)
        reclist += [', ']

    reclist[-1] = ')'
    return reclist

################################################################################
################################################################################
################################################################################

def get_query_params_from_request():
    """Extract parameters from the current Flask request.

    Returns:
        dict: Cleaned and typed parameters with defaults applied.
    """

    params = {
        'pages': request.args.get('pages'),
        'grid': request.args.get('grid'),
        'continuous': request.args.get('continuous'),
        'skip': request.args.get('skip'),
        'rows': request.args.get('rows'),
        'preview': request.args.get('preview'),
        'filter': request.args.get('filter'),
        'selection': request.args.get('selection'),
    }

    return clean_query_params(params)

def get_query_params_from_url(url):
    """Extract parameters from a URL string and normalize them.

    Parameters:
        url (str): Full or partial URL containing a query string.

    Returns:
        dict: Cleaned and typed parameters with defaults applied.
    """

    params = {
        'pages': 1,
        'grid': 0,
        'continuous': 0,
        'skip': 0,
        'rows': MAX_ROWS,
        'preview': 'default',
        'filter': '',
        'selection': '',
    }

    param_string = urllib.parse.urlparse(url).query
    new_dict = urllib.parse.parse_qs(param_string, keep_blank_values=True)
    for key in new_dict:
        if key in params:
            params[key] = new_dict[key][0]

    return clean_query_params(params)

def get_query_params_from_dict(params):
    """Normalize a parameters dictionary.

    Removes unknown keys and applies defaults for missing values, then cleans
    and types each value similarly to other parameter helpers.

    Parameters:
        params (dict): Raw parameter dictionary.

    Returns:
        dict: Cleaned and typed parameters with defaults applied.
    """

    defaults = {
        'pages': 1,
        'grid': 0,
        'continuous': 0,
        'skip': 0,
        'rows': MAX_ROWS,
        'preview': 'default',
        'filter': '',
        'selection': '',
    }

    # Remove unrecognized keys
    new_params = params.copy()
    for key in new_params:
        if key not in defaults:
            del new_params[key]

    # Fill in default values for missing keys
    for key in defaults:
        if key not in new_params:
            new_params[key] = defaults[key]

    return clean_query_params(params)

def clean_query_params(old_params):
    """Validate, coerce, and default URL parameters.

    Applies bounds and typing to grid, paging, filtering, and selection
    parameters.

    Parameters:
        old_params (dict): Raw parameters as strings/None.

    Returns:
        dict: Cleaned parameters.
    """

    # Pages allows for multiple results pages to be concatenated together,
    # starting from the one requested.
    pages = old_params['pages']
    if pages is None:
        pages = 1
    elif str(pages) == '':
        pages = 1
    else:
        try:
            pages = min(max(1, int(pages)), MAX_PAGES)
        except (TypeError, ValueError, KeyError):
            pages = 1

    # Grid selects a grid view. "grid" by itself in the URL turns on small
    # grid mode; grid=2 or greater turns on large grid mode; grid=0 returns
    # to list mode.
    grid = old_params['grid']
    if grid is None:
        grid = 0
    elif str(grid) == '':
        grid = 1
    else:
        try:
            grid = min(max(0, int(grid)), 2)
        except (TypeError, ValueError, KeyError):
            grid = 0

    # Continuous = 0 or 1 to turn on or off the dividers separating parallel
    # directories. Ignored for single-page results
    continuous = old_params['continuous']
    if continuous is None:
        continuous = 0
    elif str(continuous) == '':
        continuous = 1
    else:
        try:
            continuous = min(max(0, int(continuous)), 1)
        except (TypeError, ValueError, KeyError):
            continuous = 0

    # Skip = the number of rows in the table to skip
    # Rows = the number of rows to display
    skip = old_params['skip']
    if skip is None:
        skip = 0
    elif str(skip) == '':
        skip = 0
    else:
        try:
            skip = max(0, int(skip))
        except (TypeError, ValueError, KeyError):
            skip = 0

    rows = old_params['rows']
    if rows is None:
        rows = MAX_ROWS
    elif str(rows) == '':
        rows = MAX_ROWS
    else:
        try:
            rows = int(rows)
        except (TypeError, ValueError, KeyError):
            rows = MAX_ROWS

    # Preview = name of the preview to show; default is "default"
    preview = old_params['preview']
    if preview is None:
        preview = 'default'
    elif preview == '':
        preview = 'default'
    else:
        preview = str(preview)

    # Selection = one item to highlight
    selection = old_params['selection']
    if selection is None:
        selection = ''
    else:
        selection = str(selection)
        selection = selection.split('#')[0]
        selection = selection.split('?')[0]
        selection = selection.split('&')[0]

    params = {'pages': pages,
              'max_pages': MAX_PAGES,
              'grid': grid,
              'continuous': continuous,
              'skip': skip,
              'rows': rows,
              'max_rows': MAX_ROWS,
              'preview': preview,
              'selection': selection,
             }

    # Filter option
    filter = old_params['filter']
    if filter is None:
        filter = ''
    else:
        filter = str(filter)

    set_filter_in_params(params, filter)

    return params

FILTER_REGEX = re.compile(r'^(\w+|\?+|\*+|\-+|\.|\[\!{0,1}(\w+|\-)+])+$')

def set_filter_in_params(params, filter):
    """Validate and compile a file-name filter into parameters.

    Converts a user filter pattern into a safe URL form and a compiled regex
    when valid; otherwise clears the filter-related fields.

    Parameters:
        params (dict): Parameters to modify in-place.
        filter (str): Filter pattern from user input.

    Returns:
        None
    """

    if filter == '':
        filter = ''
        filter_for_url = ''
        filter_for_regex = None
    elif filter[0] == '.':      # can't start with dot!
        filter = ''
        filter_for_url = ''
        filter_for_regex = None
    else:
        # Validate filter as a match pattern
        filter = filter.replace('$', '?')   # '$' replaces '?' in URLs
        matchobj = FILTER_REGEX.match(filter)
        if matchobj is None:
            filter = ''
            filter_for_url = ''
            filter_for_regex = None
        else:
            filter_for_url = filter.replace('?', '$')
            filter_for_regex = fnmatch.translate(filter)

    try:
        filter_regex = re.compile(filter_for_regex, re.IGNORECASE)
    except (KeyError, TypeError, AttributeError):
        filter = ''
        filter_for_url = ''
        filter_regex = None

    params['filter'] = filter
    params['filter_for_url'] = filter_for_url
    params['filter_regex'] = filter_regex

    return

################################################################################

def url_params(params, selection=None):
    """Serialize parameters for inclusion in a URL.

    Skips parameters that are at default values and optionally overrides the
    selection anchor.

    Parameters:
        params (dict): Clean parameters.
        selection (str|None): Optional replacement selection anchor.

    Returns:
        str: URL suffix beginning with '?' and optional '#anchor'.
    """

    params = clean_query_params(params)

    # Update the selection if one is provided
    if selection is not None:
        params = params.copy()
        params['selection'] = selection

    # Generate a list of parameter=value strings
    url_param_list = []
    if params['pages'] > 1:
        url_param_list.append('pages=' + str(min(params['pages'], MAX_PAGES)))
    if params['grid']:
        url_param_list.append('grid=' + str(params['grid']))
    if params['continuous']:
        url_param_list.append('continuous=1')
    if params['skip']:
        url_param_list.append('skip=' + str(max(0,params['skip'])))
    if params['rows'] != MAX_ROWS:
        url_param_list.append('rows=' + str(params['rows']))
    if params['preview'] != 'default':
        url_param_list.append('preview=' + params['preview'])
    if params['selection']:
        selection_escaped = html.escape(params['selection'], quote=True)
        url_param_list.append('selection=' + selection_escaped)
    if params['filter'] != '':
        url_param_list.append('filter=' + params['filter_for_url'])

    # Merge the strings
    if len(url_param_list) > 0:
        url_param_string = '?' + '&'.join(url_param_list)
    else:
        url_param_string = ''

    # Insert the selection as a jump point into the page
    if params['selection']:
        url_param_string += '#' + selection_escaped

    return url_param_string

################################################################################
################################################################################
# FORM SETUP
################################################################################
################################################################################

FILTER_REGEX = re.compile(r'^(\w+|\?+|\*+|\-+|\.|\[(\w+|\-)+])+$')

def pattern_validator(field):
    """WTForms validator for the file-name filter pattern.

    Parameters:
        field (wtforms.Field): Field being validated.

    Raises:
        wtforms.validators.ValidationError: If the pattern is invalid.

    Returns:
        None
    """

    filter = field.data
    if filter is None: return
    filter = str(filter)

    if len(filter) == 0: return

    matchobj = FILTER_REGEX.match(filter)
    if matchobj is None:
        raise wtforms.validators.ValidationError("")

    return

class FilterForm(FlaskForm):
    """Filter form for file-name pattern and stateful redirect.

    Fields:
        filter (StringField): Optional file name match expression.
        hidden (HiddenField): Hidden field carrying the current URL.
    """

    filter = StringField('File name filter', [pattern_validator])
    hidden = HiddenField('hidden')

################################################################################

@app.route('/set_filter', methods=['POST'])
def set_filter():
    """Handle filter submission and redirect to updated URL.

    Returns:
        werkzeug.wrappers.response.Response: Redirect response.
    """

    form = FilterForm()
    if not form.validate_on_submit():
        flash('Invalid match expression: <font face="Courier">' +
              str(form.data['filter'] + '</font>'))

    url = str(form.data['hidden'])
    params = get_query_params_from_url(url)
    set_filter_in_params(params, str(form.data['filter']))

    base_url = url.split('?')[0]
    new_url = base_url + url_params(params)

    return redirect(new_url)

# The following routes will only be activated in a test environment, because
# in a production environment the Apache server will catch these URLs before
# they get to Viewmaster and serve the directly. They are included here so
# that Viewmaster can be tested without an Apache server running.

@app.route('/icons-local/<path:query_path>')
def return_icons_local(query_path):
    """Serve local icon PNGs when running without Apache static routing.

    Parameters:
        query_path (str): Relative icon path under `icons/`.

    Returns:
        Response: File response with image/png mimetype.
    """

    return send_file(f'../icons/{query_path}', mimetype='image/png')

@app.route('/holdings/<path:query_path>')
def return_holdings_local(query_path):
    """Serve holdings files directly when running locally.

    Parameters:
        query_path (str): Path under the holdings root.

    Returns:
        Response: File response with appropriate MIME type.
    """

    global HOLDINGS_PATHS

    root_dir = HOLDINGS_PATHS[0]
    mimetype, _ = mimetypes.guess_type(query_path)
    return send_from_directory(root_dir, query_path, mimetype=mimetype)

@app.route('/feedback/<path:query_path>')
def return_feedback(query_path):
    """Redirect to the external feedback page.

    Parameters:
        query_path (str): Path suffix after `/feedback/`.

    Returns:
        Response: Redirect response to site feedback page.
    """

    return redirect(f'https://pds-rings.seti.org/feedback/{query_path}')

################################################################################
################################################################################
################################################################################

@app.route('/', defaults={'query_path': ''})
@app.route('/<path:query_path>')
def viewmaster(query_path):
    """Main route handler rendering directory or product pages.

    Applies caching, normalizes the URL, and renders the appropriate view.

    Parameters:
        query_path (str): Logical PDS path with optional query string.

    Returns:
        str|Response|tuple: HTML page, redirect, or 404 page.
    """

    global LOGGER, PAGE_CACHE

    # This can happen during testing
    if query_path.endswith('favicon.ico'): return ''

    # Get query parameters
    query_path = query_path.rstrip('/')
    original_query_path = query_path
    params = get_query_params_from_request()
    query_parts = query_path.split('?')
    query_path = query_parts[0]
    suffix = url_params(params)
    key = '#' + query_path + suffix

    # Return page from cache if available
    if PAGE_CACHE:
        try:
            html = zlib.decompress(PAGE_CACHE[key]).decode('utf-8', 'ignore')

            # Log query
            LOGGER.info('Request: %s (from cache)' % key[1:])
            return html

        except KeyError:
            pass

        except Exception as e:
            LOGGER.exception(e)
            pass

    # Generate page
    query_pdsfile = None
    start_time = datetime.datetime.now()
    # pdsfile.pause_caching()   # XXX NEEDS TO BE UPDATED

    stacktrace = True
    try:
        # Interpret the query
        must_exist = '.tab/' not in query_path.lower()
        query_pdsfile = pdsfile.Pds3File.from_path(query_path,
                                                   must_exist=must_exist)

        if not query_pdsfile.is_index_row and not query_pdsfile.exists:
            raise OSError('Unidentified PdsFile failure')

        # If the URL has changed, redirect
        if query_pdsfile.logical_path != query_path:
            new_query_path = query_pdsfile.logical_path + suffix
            elapsed = (datetime.datetime.now() - start_time).total_seconds()
            seconds = (' ' + int(elapsed)*'#').rstrip()

            LOGGER.info('Redirecting to new target %s: %s (%5.3fs)%s' %
                        (new_query_path, key[1:], elapsed, seconds))
            return redirect(VIEWMASTER_PREFIX_ + new_query_path)

        # Otherwise, generate page
        if query_pdsfile.isdir:
            response = directory_page_html(query_pdsfile, params, LOGGER)
        else:
            response = product_page_html(query_pdsfile, params, LOGGER)

        # Check for possible redirect
        if isinstance(response, tuple):
            new_query_path = response[1]
            elapsed = (datetime.datetime.now() - start_time).total_seconds()
            seconds = (' ' + int(elapsed)*'#').rstrip()

            LOGGER.info('Redirecting for new params %s: %s (%5.3fs)%s' %
                        (key[1:], new_query_path, elapsed, seconds))
            return redirect(VIEWMASTER_PREFIX_ + new_query_path)

        html = response
        if TRIM_HTML:
            html = trim_html(html)

        if PAGE_CACHE:
            PAGE_CACHE[key] = zlib.compress(html.encode('utf-8', 'ignore'))

        # Log query
        elapsed = (datetime.datetime.now() - start_time).total_seconds()
        seconds = (' ' + int(elapsed)*'#').rstrip()

        LOGGER.info('Request: %s (%5.3fs)%s' % (key[1:], elapsed, seconds))

        return html

    except Exception as e:
        LOGGER.exception(e, original_query_path, stacktrace=stacktrace)

        # Log query failure
        LOGGER.warning('File not found', original_query_path)

        # Log the referring page if available
        http_referrer = os.environ.get('HTTP_REFERER','')
        if http_referrer:
            LOGGER.info('Referring page: ' + http_referrer)

        # Try to return a fancy index; this works if the file exists and will
        # fail otherwise
        if query_pdsfile is not None:
            try:
                url = query_pdsfile.html_root_ + query_pdsfile.logical_path
                LOGGER.info('Returning fancy index', url)
                return redirect(url + '?viewmaster_referrer=' + http_referrer)
            except Exception:
                LOGGER.warning('Fancy index unavailable; abort(404)')


        # Return a 404 page but don't abort the process!
        LOGGER.warning('ABORT 404')
        return render_template('error.html', query_parts=query_parts), 404

    finally:
        pass
        # pdsfile.resume_caching()  # XXX NEEDS TO BE UPDATED

################################################################################
# Use /viewmaster/--build-cache to cache all the pdsdata volumes down to their
# data directories.
################################################################################

SALT = b'41fc142aaf094d39'  # from random.org
DIGEST = '448b293a2708e6a6a295daf7da35422803bfa6daf2a9db78d202ccd986b3542f'
# n-----D

@app.route('/--build-cache', methods=['POST','GET'])
def build_cache():
    """Expand caches for commonly accessed pages.

    Protected by a password submitted via form; may take considerable time.

    Returns:
        str|Response: Status text or template response.
    """

    global LOGGER

    # When the page is first loaded, request.method == "GET"
    # Upon filling in the password and clicking on "Enter", method == "POST"

    if request.method == 'GET':
        LOGGER.info('Viewmaster cache builder page loaded')
        return render_template('build_cache.html')

    try:
        password = request.form['password']
        hasher = hashlib.sha256()
        hasher.update(SALT)
        hasher.update(bytes(password, 'latin-1'))
        if hasher.hexdigest() == DIGEST:
            initialize_caches(reset=False)
            fill_page_cache()
            LOGGER.info('Viewmaster cache building completed')
            return 'Viewmaster cache building completed'
        else:
            LOGGER.error('Viewmaster cache building canceled')
            return 'Viewmaster cache building FAILED'

    except Exception as e:
        LOGGER.exception(e, '--build-cache', stacktrace=True)
        return 'Viewmaster cache building FAILED'

@app.route('/--build-local-cache', methods=['POST','GET'])
def build_local_cache():
    """Build caches when initiated from a local network address.

    Returns:
        str: Status text.
    """

    global LOGGER

    ip_address = str(request.remote_addr)
    if (ip_address.startswith(LOCAL_IP_ADDRESS_A_B_C) or
        (EXTRA_LOCAL_IP_ADDRESS_A_B_C is not None and
         ip_address.startswith(EXTRA_LOCAL_IP_ADDRESS_A_B_C))):
        LOGGER.info('Viewmaster cache building initiated locally', ip_address)
        try:
            initialize_caches(reset=False)
            fill_page_cache()
            LOGGER.info('Viewmaster cache building completed')
            return 'Viewmaster cache building completed'
        except Exception as e:
            LOGGER.exception(e, '--build-local-cache', stacktrace=True)
            return 'Viewmaster cache building FAILED'

    else:
        LOGGER.error('Invalid local IP address for building Viewmaster cache',
                     ip_address)
        return 'Viewmaster cache building FAILED'

def fill_page_cache():
    """Pre-render and cache top-level and large directory pages.

    Walks holdings to warm the page cache for faster subsequent access.

    Returns:
        None
    """

    global PAGE_CACHE

    # Process un-versioned (latest) volsets first, then versioned
    unversioned_volset_pdsfiles = []
    versioned_volset_pdsfiles = []
    for voltype in ('volumes', 'calibrated', 'previews', 'diagrams'):
        voltype_pdsf = Pds3File.from_logical_path(voltype)
        _ = viewmaster(voltype)

        for volset_name in voltype_pdsf.childnames:
            volset_pdsf = voltype_pdsf.child(volset_name)
            _ = viewmaster(volset_pdsf.logical_path)

            if '_v' in volset_name:
                versioned_volset_pdsfiles.append(volset_pdsf)
            else:
                unversioned_volset_pdsfiles.append(volset_pdsf)

    for volset_pdsf in unversioned_volset_pdsfiles + versioned_volset_pdsfiles:
        for volume_name in volset_pdsf.childnames:
            volume_pdsf = volset_pdsf.child(volume_name)
            _ = viewmaster(volume_pdsf.logical_path)

            data_count = 0
            for childname in volume_pdsf.childnames:
                childname_lc = childname.lower()
                if 'data' not in childname_lc or childname_lc.endswith('.txt'):
                    continue

                data_count += 1
                _ = viewmaster(volume_pdsf.logical_path + '/' + childname)

                # If this directory is too small, cache the subdirectories too
                # This covers big subdirectories like "EDR", "RDR", "TSDR", etc.
                data_pdsf = volume_pdsf.child(childname)
                if len(data_pdsf.childnames) <= 5:
                    for name in data_pdsf.childnames:
                        if '.' not in name:
                            _ = viewmaster(data_pdsf.logical_path + '/' + name)

            # If no subdirectory contains "data", just cache every directory
            if data_count == 0:
                for childname in volume_pdsf.childnames:
                    if '.' in childname:
                        continue

                    _ = viewmaster(volume_pdsf.logical_path + '/' + childname)

    if PAGE_CACHE:
        PAGE_CACHE.flush()

################################################################################
# Use /viewmaster/--reset to empty the cache and reload the minimal pdsdata
# tree.
################################################################################

@app.route('/--reset-cache', methods=['POST','GET'])
def reset_cache():
    """Reset caches to an initial state.

    Protected by a password submitted via form.

    Returns:
        str|Response: Status text or template response.
    """

    global LOGGER

    # When the page is first loaded, request.method == "GET"
    # Upon filling in the password and clicking on "Enter", method == "POST"

    if request.method == 'GET':
        LOGGER.info('Viewmaster cache reset page loaded')
        return render_template('reset_cache.html')

    try:
        password = request.form['password']
        hasher = hashlib.sha256()
        hasher.update(SALT)
        hasher.update(bytes(password, 'latin-1'))
        if hasher.hexdigest() == DIGEST:
            initialize_caches(reset=True)
            LOGGER.info('Viewmaster cache reset completed')
            return 'Viewmaster cache reset completed'
        else:
            LOGGER.error('Viewmaster cache reset canceled')
            return 'Viewmaster cache reset FAILED'

    except Exception as e:
        LOGGER.exception(e, '--reset-cache', stacktrace=True)
        return 'Viewmaster cache reset FAILED'

################################################################################

@app.route('/--hexdigest', methods=['POST','GET'])
def hexdigest():
    """Utility to compute and display the SHA-256 hexdigest of a password.

    Returns:
        str|Response: Hex digest string on POST; form template on GET.
    """

    if request.method == 'POST':
        password = request.form['password']
        hasher = hashlib.sha256()
        hasher.update(SALT)
        hasher.update(bytes(password, 'latin-1'))
        return 'The hexdigest of "' + password + '" is ' + hasher.hexdigest()

    else:
        return render_template('hexdigest.html')

################################################################################
# A utility to reduce HTML page size, because the Jinja2 directives don't seem
# to work for me.
#
#jinja2: trim_blocks: True, lstrip_blocks: True
################################################################################

def trim_html(html):
    """Minify HTML by trimming whitespace outside of <pre> blocks.

    Parameters:
        html (str): Raw HTML string.

    Returns:
        str: Trimmed HTML.
    """

    old_html_recs = html.split('\n')
    new_html_recs = []
    preformatted = False

    for rec in old_html_recs:
        if '<pre>' in rec or '<pre ' in rec:
            preformatted = True

        if preformatted:
            new_html_recs.append(rec)
        else:
            rec = rec.strip()
            if rec:
                new_html_recs.append(rec)

        if '</pre>' in rec:
            preformatted = False

    return '\n'.join(new_html_recs)

################################################################################

if __name__ == "__main__":
    logger = get_or_create_logger()
    pdsviewable.load_icons(path=ICON_ROOT_, url=ICON_URL_, color=ICON_COLOR,
                           logger=logger)

    HOLDINGS_PATHS = get_holdings_path(logger)
    PAGE_CACHE = get_page_cache(logger)

    initialize_caches(reset=False)
    app.run(host='0.0.0.0', port=8080, debug=True)

################################################################################
