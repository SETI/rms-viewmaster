# Viewmaster Help Guide

Version 1.0
October 2025

# Viewmaster

## Overview

**Viewmaster** is a web-based file and document viewer and management tool. It is focused on handling and displaying various types of PDS documents and folders.

---

# Running Viewmaster

## Environment Setup (first-time only)

1. Clone the repository:
   ```bash
   git clone https://github.com/SETI/rms-viewmaster.git
   ```

2. Create a virtual environment and install dependencies in the `rms-viewmaster` directory:
   ```bash
   python -m venv myenv        # Replace "myenv" with your preferred name
   source myenv/bin/activate
   pip install -r requirements.txt
   ```

3. Set the environment variable `PDS3_HOLDINGS` to the path of your PDS3 holdings.

---

## Running Locally

1. Start the server:
   ```bash
   sudo -E python viewmaster/viewmaster.py
   ```

2. Open your browser and go to:
   [http://127.0.0.1:8080/](http://127.0.0.1:8080/)
   *(This corresponds to `VIEWMASTER_PREFIX_` in `viewmaster_config.py`.)*

---

# Key Components

## 1. Main Application Code (`viewmaster/`)
- **Python Modules:**
  - `link.py`, `pdsgroup.py`, `pdsgrouptable.py`, `pdsiterator.py`: Handle core logic for grouping, iterating, and linking PDS documents or datasets.
  - `viewmaster.py`, `viewmaster-without-pause.py`: Main entry points and application logic for the viewer.
  - `viewmaster_config.py`: Configuration settings for the application.

- **Templates (`viewmaster/templates/`):**
  - HTML files for rendering views: tables, grids, navigation, error pages, feedback, etc.
  - These templates provide the web interface, including navigation, table/grid views, and feedback/error handling.

## 2. Static Assets (`icons/`)
- Organized by color (black, blue, gray) and size (30, 50, 100, 200, 500).
- Icons for document types (archive, binary, book, image, PDF, software, etc.) and folders (archives, binary, cubes, diagrams, etc.).
- Used for visually representing files and folders in the UI.

## 3. Web Server Integration
- `viewmaster.wsgi`, `link.wsgi`, `wsgi_init.py`: WSGI entry points for deploying the application with a WSGI-compatible web server.

## 4. Project Metadata
- `README.md`: Project overview and instructions.
- `requirements.txt`: Python dependencies.
- `LICENSE`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`: Standard open-source project files.

---

# Summary of the Core Python Files

## `viewmaster.py` and `viewmaster-without-pause.py`

### Overview
`viewmaster.py` is the core module of the application. It sets up a Flask-based server that serves as a document viewer for PDS files. Users can browse, view, and navigate through a hierarchical structure of files and folders, with support for multiple document types and metadata.

`viewmaster-without-pause.py` is a variant designed to run without pausing or waiting for user input.

### Key Components and Functionality

1. **Imports and Initialization**
   - Imports Flask and related modules (FlaskForm, StringField, HiddenField) for web handling and form processing.
   - Imports utility modules (os, sys, logging, psutil, etc.) and custom modules (pdsfile, pdsiterator, pdslogger, pdstable, pdsgroup, pdsgrouptable).
   - Initializes the Flask app with a secret key and configuration values (like `LOCAL_IP_ADDRESS`).
   - Imports configuration parameters (e.g., `LOCALHOST_`, `VIEWMASTER_PREFIX_`, `WEBSITE_HTTP_HOME`) from `viewmaster_config.py`.
   - Configures logging with `pdslogger`, with separate log files for info and debug levels.

2. **Constants and Configuration**
   - Defines constants such as `ICON_ROOT_`, `ICON_URL_`, and `VIEWABLE_EXTENSIONS`.
   - Defines `ASSOCIATED_CATEGORIES` for navigation and grouping.
   - Sets UI and navigation limits (`MAX_PAGES`, `MAX_NAV_STRLEN`, etc.).

3. **Holdings Path Management**
   - `get_holdings_paths()` reads the Apache configuration file (or environment variable) to determine the holdings directories.
   - `validate_holdings_paths()` checks for existence and logs warnings/errors.
   - `create_holdings_symlinks()` likely creates symbolic links for easier access.

4. **Cache Initialization**
   - Functions like `initialize_caches()`, `build_cache()`, and `reset_cache()` manage caching for performance.
   - Uses memcached (via `pylibmc`) for caching.

5. **Navigation and Page Generation**
   - Functions such as `get_prev_next_navigation()`, `list_next_pdsfiles()`, and `fill_level_navigation_links()` generate navigation links.
   - `get_directory_page()` and `directory_page_html()` render directory listings.
   - `get_product_page_info()` and `product_page_html()` render product pages.

6. **URL Parameter Handling**
   - Functions like `get_query_params_from_request()`, `get_query_params_from_url()`, and `clean_query_params()` parse and sanitize URL parameters.
   - `url_params()` constructs URLs with the proper parameters.

7. **Form Handling**
   - Defines a `FilterForm` class (Flask-WTF) for file name filtering.
   - The `/set_filter` route processes POST requests to update filters.

8. **Route Definitions**
   - The main route (`@app.route('/<path:query_path>')`) handles all incoming requests.
   - Additional routes handle filtering, serving icons, holdings, and feedback.

9. **Utility Functions**
   - Functions like `format_row_value()` and `format_tuple()` prepare data for display.
   - `trim_html()` likely cleans up HTML for rendering.

---

## `viewmaster_config.py`

### Overview
`viewmaster_config.py` is the configuration module for Viewmaster. It defines environment-specific settings (URLs, logging, caching) based on whether the app is in testing, local, or production mode.

### Key Components and Functionality
1. **Environment Detection**
   - Uses `platform` and `socket` to detect OS and hostname.
   - Flags like `VIEWMASTER_TESTING` and `VIEWMASTER_FOR_MARK` determine the environment.

2. **Configuration Blocks**
   - **Testing**: Localhost URLs, caching disabled, log name `pds.viewmaster.testing`.
   - **Local**: Custom localhost URLs, symlinks enabled, caching disabled, log name `pds.viewmaster.local`.
   - **Production**: Deployment URLs, symlinks enabled, caching disabled, log name `pds.viewmaster.server`.

3. **Platform-Specific Settings**
   - Linux: uses `/var/run/memcached/memcached.socket`, `/var/www/` paths, Apache config in `/etc/apache2/`.
   - macOS: uses `/var/tmp/memcached.socket`, `/Library/WebServer/` paths, Apache config in `/usr/local/etc/httpd/`.

4. **Other Settings**
   - `USE_SHELVES_ONLY = False` (application supports multiple storage mechanisms).

---

## `link.py`

### Overview
`link.py` is a Flask-based microservice for URL redirection. It redirects requests either to the main Viewmaster app (for directories) or directly to files.

### Key Components and Functionality
1. **Imports and Initialization**
   - Uses Flask (redirect, abort), os, glob, logging, and `pdslogger`.
   - Imports configuration from `viewmaster_config.py`.

2. **Logging Configuration**
   - Log name derived from Viewmaster config, replacing "viewmaster" with "link".
   - Configured for rotating log files.

3. **Route Definitions**
   - Main route: `/path:query_path>` defaults to `volumes`.
   - Determines whether to redirect to a directory view or directly to a file.

4. **Redirection Logic**
   - If a directory: redirects to `VIEWMASTER_PREFIX_ + query_path`.
   - If a file: finds file via glob, then redirects to `WEBSITE_HTTP_HOME + relative path`.
   - If missing: logs error and returns 404.

---

## `pdsgroup.py`

### Overview
`pdsgroup.py` defines the `PdsGroup` class for managing an ordered set of `PdsFile` objects. Groups related files (e.g., a file and its label) for display in the UI.

### Key Components
- **Initialization**: Stores parent directory, anchor, and files.
- **Methods**:
  - `__len__`, `__repr__`, `copy()`.
  - Sorting (`sort()`), grouping (`group_children()`).
  - File management (`append()`, `remove()`, `hide()`, `unhide()`).
  - Iterators for visible/hidden/all files.
- **Icons/Viewsets**: Manages closed/open states and viewable sets.

---

## `pdsgrouptable.py`

### Overview
`pdsgrouptable.py` defines the `PdsGroupTable` class for managing an ordered set of `PdsGroup` objects. It organizes groups into tables for display.

### Key Components
- **Initialization**: Stores groups and parent.
- **Methods**:
  - `__repr__`, `copy()`.
  - Insert groups/files (`insert_group`, `insert_file`, `insert()`).
  - Sorting (`sort_in_groups`, `sort_groups`).
  - File/group hiding/removal.
  - Iterators for groups/files.
- **Static Methods**:
  - `sort_tables()`, `tables_from_pdsfiles()`, `merge_index_row_tables()`.

---

## `pdsiterator.py`

### Overview
`pdsiterator.py` provides three main iterator classes for navigating through PDS file structures.

### Key Components and Functionality
- **PdsDirIterator** (lines 29-144)
    - **Purpose**: Iterates across related directories, jumping into adjacent directories and parallel volumes
    - **Key Features**:
        - Uses a global `DIRECTORY_CACHE` to optimize performance by caching directory listings
        - Supports both forward and backward iteration (via `sign` parameter)
        - Handles case-insensitive path matching
        - Returns tuples of `(logical_path, display_path, level)` where:
            - `level = 0`: same directory level
            - `level = 1`: different directory level
        - Uses `pdsfile.NEIGHBORS` to find related directories using fnmatch patterns

- **PdsFileIterator** (lines 150-268)
    - **Purpose**: Iterates through files within directories, with support for jumping to adjacent directories when needed
    - **Key Features**:
        - Supports pattern matching and filtering of file names
        - Can exclude files based on patterns
        - Supports custom filter functions
        - Handles "cousin" navigation (jumping to adjacent parent directories)
        - Returns tuples with level indicators:
            - `level = 0`: sibling files (same directory)
            - `level = 1`: cousin files (different directory)

- **PdsRowIterator** (lines 274-336)
    - **Purpose**: Simple iterator for files within a single directory (siblings only)
    - **Key Features**:
        - More lightweight than `PdsFileIterator`
        - Only iterates within the same parent directory
        - Always returns `level = 0` since it doesn't cross directory boundaries

- **Utility Functions:**
    - **`dirs_only()`** (lines 12-16): Filter function that only returns directories

- **Key Design Patterns:**
    1. **Caching**: Uses `DIRECTORY_CACHE` to avoid repeated expensive directory operations
    2. **Case-insensitive matching**: All path comparisons are done in lowercase
    3. **Iterator protocol**: All classes implement `__iter__()`, `__next__()`, and `next()` methods
    4. **Cloning**: Each iterator has a `copy()` method for creating reversed or modified versions
    5. **Flexible navigation**: Supports both forward (`sign=1`) and backward (`sign=-1`) iteration

---
