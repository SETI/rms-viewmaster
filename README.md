<!-- start-after-point -->

<!-- Add badges once PyPI, GitHub Actions, and Codecov exist -->
<!--
| PyPI Release | Test Status | Code Coverage |
|--------------|-------------|----------------|
| [![PyPI version](https://badge.fury.io/py/rms-viewmaster.svg)](https://badge.fury.io/py/rms-viewmaster) | [![Build status](https://img.shields.io/github/actions/workflow/status/SETI/rms-viewmaster/run-app-tests.yml?branch=main)](https://github.com/SETI/rms-viewmaster/actions) | [![Code coverage](https://img.shields.io/codecov/c/github/SETI/rms-viewmaster/main?logo=codecov)](https://codecov.io/gh/SETI/rms-viewmaster) |
-->

# Introduction

`Viewmaster` is a web‑based file and document viewer and management tool. It focuses on handling and displaying various types of PDS documents and folders.

# Getting Started

Environment Setup (first‑time only)

1. Clone the repository:

   ```bash
   git clone https://github.com/SETI/rms-viewmaster.git
   ```

2. Create a virtual environment and install dependencies:

   ```bash
   cd rms-viewmaster
   python -m venv myenv        # Replace "myenv" with your preferred name
   source myenv/bin/activate
   pip install -r requirements.txt
   # or, for an editable install that also provides the `viewmaster` CLI:
   pip install -e .
   ```

   Optional extras:

   - Tests and docs: `pip install -r requirements-dev.txt` (or `pip install -e '.[dev]'`). Sphinx 9 / myst-parser 5 need Python 3.12+.
   - Memcached page caching: `pip install -e '.[memcache]'` (needs `libmemcached` headers, e.g. Debian/Ubuntu `libmemcached-dev`). `pylibmc` is **not** required for clone-and-run.

3. Set required environment variables.

   Set `PDS3_HOLDINGS_DIR` to the path of your PDS3 holdings directory.

   After symlink resolution (`realpath`), this path **must** end with a directory named `holdings`.

   Optionally set `PDS4_HOLDINGS_DIR` to a directory named `pds4-holdings` (after `realpath`). When set, Viewmaster preloads that tree via `Pds4File` at startup.

4. Logs in local-dev/testing mode are written under `$XDG_STATE_HOME/viewmaster/` (or `~/.local/state/viewmaster/` if `XDG_STATE_HOME` is unset). Override with `VIEWMASTER_LOG_DIR`. You do **not** need to create `/var/www` or `/Library/WebServer` for local development.

Running Locally

1. Start the server at the root of the repo:

   ```bash
   viewmaster
   # or, without an editable install:
   python -m viewmaster.viewmaster
   # or:
   python -m viewmaster
   ```

2. Open your browser and go to:

   <http://127.0.0.1:8080/>
   *(This corresponds to `VIEWMASTER_PREFIX_` in `viewmaster_config.py`.)*

   The server binds to `127.0.0.1:8080` by default. Override with `VIEWMASTER_HOST` and `VIEWMASTER_PORT` (for example `VIEWMASTER_HOST=0.0.0.0` to listen on all interfaces).

   `python -m viewmaster.viewmaster` and the `viewmaster` CLI enable testing mode automatically (localhost URLs, memcache disabled, user-writable log dir). When running under `flask run`, gunicorn, or pytest, set `VIEWMASTER_TESTING=1` (also accepts `true` or `yes`) so the same local-dev config is used. Set `VIEWMASTER_TESTING=0` to force production config even for the CLI.

   Set `VIEWMASTER_SECRET_KEY` in production. Local command-line runs fall back to a built-in development key.

   Production paths and URLs (`VIEWMASTER_DOCUMENT_ROOT`, `VIEWMASTER_LOG_DIR`, `VIEWMASTER_WEBSITE_HTTP_HOME`, `VIEWMASTER_URL_PREFIX`, `VIEWMASTER_MEMCACHE_PORT`, `PDSFILE_MEMCACHE_PORT`, `VIEWMASTER_EXTRA_LOCAL_IP`) can be overridden with environment variables; see `viewmaster/viewmaster_config.py`.

# Deploying with Apache / WSGI

Production deployment uses Apache with mod_wsgi. `create_app()` performs all startup (logger, holdings paths, page cache, icons, and Pds3File/Pds4File preload), so the WSGI files are two-line factories with no separate init script.

WSGI entry points (at the repo root):

- [`viewmaster.wsgi`](viewmaster.wsgi) — Viewmaster
- [`link.wsgi`](link.wsgi) — Link redirect service

Point `WSGIDaemonProcess` `python-home` at the virtualenv that has `requirements.txt` installed (`pip install -r requirements.txt` or `pip install .`). Add `pip install '.[memcache]'` on the production host if page caching via memcached is enabled. That is how the daemon finds Python packages; there is no `wsgi_init.py` venv bootstrap.

## Environment variables

These must be in the **Apache process environment** (`os.environ`) so `create_app()` can read them at import time. `SetEnv` in a vhost only fills the WSGI request environ and is **not** sufficient.

| Variable | Required | Notes |
|----------|----------|--------|
| `PDS3_HOLDINGS_DIR` | Yes | Absolute path to the PDS3 holdings directory (same layout as in Getting Started). |
| `PDS4_HOLDINGS_DIR` | No | Absolute path to a directory named `pds4-holdings`. When set, `Pds4File` is preloaded at startup. |
| `VIEWMASTER_SECRET_KEY` | Yes in production | Flask secret key. `create_app()` raises if this is unset unless `VIEWMASTER_TESTING` is enabled. |
| `VIEWMASTER_LOG_DIR` | No | Directory for log files (defaults to `/var/www/logs/webapps/` on Linux). |

Do **not** set `VIEWMASTER_TESTING` in production (that switches on localhost URLs and disables memcache).

Example for Debian/Ubuntu (`/etc/apache2/envvars`):

```bash
export PDS3_HOLDINGS_DIR=/var/www/documents/holdings
# export PDS4_HOLDINGS_DIR=/var/www/documents/pds4-holdings
export VIEWMASTER_SECRET_KEY=replace-me
```

On systemd-managed Apache (RHEL/CentOS/Fedora), use a drop-in with `Environment=` or `EnvironmentFile=` lines instead.

## Example vhost

A complete template is in [`examples/apache2/viewmaster.conf`](examples/apache2/viewmaster.conf). Replace `/path/to/venv` and `/path/to/rms-viewmaster`, then enable the site and `mod_wsgi`.

```apache
WSGIDaemonProcess viewmaster \
    python-home=/path/to/venv \
    python-path=/path/to/rms-viewmaster \
    processes=2 \
    threads=5 \
    display-name=%{GROUP}

WSGIScriptAlias /viewmaster /path/to/rms-viewmaster/viewmaster.wsgi \
    process-group=viewmaster application-group=%{GLOBAL}
```

The `/viewmaster` mount matches the production URL prefix (`VIEWMASTER_PREFIX_` is `/viewmaster/`). `python-home` must be the venv created in Getting Started (or an equivalent production venv). The example vhost also defines a second daemon and `/link` alias for [`link.wsgi`](link.wsgi).

# Viewmaster and `PdsFile` Rules Interface

Viewmaster renders pages by building a `page` dictionary and passing it
to Jinja templates. Most values in this dictionary are derived from
`pdsfile.Pds*File` objects and from bundle-specific rule definitions.

Each Jinja template consumes specific `page[...]` keys to render
different sections of the interface.

A typical Viewmaster page contains three main tables:

1.  Main file table
2.  Related files table
3.  Documentation table

Additional sections include the information panel and neighbor
navigation bar.

------------------------------------------------------------------------

# Rendering Architecture

The overall rendering flow is:

    PdsFile rules
          │
          ▼
    Viewmaster builds page dictionary
          │
          ▼
    Jinja templates render page sections
          │
          ├── Main file table
          ├── Related files table
          ├── Documentation table
          ├── Info section
          └── Neighbor navigation

------------------------------------------------------------------------

# Main File Table

`page['tables']`

![main_table](README_icon/main_table.png)

## Rendering

Rendered by:

    viewmaster/templates/table_div.html

Within this template:

    tables + associations + documents → all_tables

## Included from

-   `viewmaster/templates/table_view.html`
-   `viewmaster/templates/grid_view.html`
-   `viewmaster/templates/index_rows_view.html`

## Rules affecting this table

### SORT_KEY

- Bundle-specific variable: `sort_key`

- Defines how basenames are ordered. This determines the order of the table rows.

### SPLIT_RULES

- Bundle-specific variable: `split_rules`

- Defines how a basename is split into: anchor/suffix/extension. Files with the same anchor are grouped together. Within a group, ordering is determined by `SORT_KEY`.

### DESCRIPTION_AND_ICON

- Bundle-specific variable: `description_and_icon_by_regex`

- Defines the icon and description displayed for each table row.

These three rules apply to all tables on the page.

------------------------------------------------------------------------

# Related Files Table

`page['associations']`

![associations](README_icon/associations.png)

This table appears under **"Related files:"**.

## Rendering

Rendered by:

    viewmaster/templates/table_div.html

(as part of `all_tables`)

## Rules affecting this table

### ASSOCIATIONS

- Bundle-specific variables: `associations_to_*` (excluding `associations_to_documents`)

- For a given `PdsFile` instance, these rules define which files should
appear in the Related files table.

------------------------------------------------------------------------

# Documentation Table

`page['documents']`

![documents](README_icon/documents.png)

This table appears under **"Documentation:"**.

## Rendering

Rendered by:

    viewmaster/templates/table_div.html

(as part of `all_tables`)

## Rules affecting this table

### ASSOCIATIONS (documents)

- Bundle-specific variable: `associations_to_documents`

- This rule defines which files should appear in the Documentation table
for a given `PdsFile` instance.

------------------------------------------------------------------------

# Info Section

`page['info']`\
`page['info_content']`

![info](README_icon/info.png)

## Rendering

Rendered by:

    viewmaster/templates/info_div.html

## Rules affecting this section

### INFO_FILE_BASENAMES

- Defines the file basename whose contents will be rendered at the end of the page when the basename appears in the main table.

------------------------------------------------------------------------

# Neighbor Navigation

Horizontal navigation bar displayed above the first table.

![nav](README_icon/nav.png)

## Rendering

Rendered by:

    viewmaster/templates/neighbor_navigation.html

Included from:

    table_div.html

## Rules affecting this section

### NEIGHBORS

- Defines adjacent directories in the navigation bar. Used when the current page corresponds to: a directory or an index row.

### SIBLINGS

- Defines adjacent files in the navigation bar. Used when the current page corresponds to a file.

------------------------------------------------------------------------

# Summary


  | Page Section     | Page Key               | Main Rules                                         |
  |------------------|------------------------|----------------------------------------------------|
  | Main file table  | `page['tables']`       | `SORT_KEY`, `SPLIT_RULES`, `DESCRIPTION_AND_ICON`  |
  | Related files    | `page['associations']` | `ASSOCIATIONS`                                     |
  | Documentation    | `page['documents']`    | `associations_to_documents`                        |
  | Info section     | `page['info']`         | `INFO_FILE_BASENAMES`                              |
  | Navigation bar   | ---                    | `NEIGHBORS`, `SIBLINGS`                            |


# Contributing

Information on contributing to this package can be found in the
[Contributing Guide](https://github.com/SETI/rms-viewmaster/blob/main/CONTRIBUTING.md).

# Links
- [Documentation](https://rms-viewmaster.readthedocs.io/en/latest/)
- [Repository](https://github.com/SETI/rms-viewmaster)
- [Issue tracker](https://github.com/SETI/rms-viewmaster/issues)
<!-- Add this once we make pip install working -->
<!-- - [PyPi](https://pypi.org/project/rms-viewmaster) -->
