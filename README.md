<!-- start-after-point -->

| PyPI Release | Test Status | Code Coverage |
|--------------|-------------|----------------|
| [![PyPI version](https://badge.fury.io/py/rms-viewmaster.svg)](https://badge.fury.io/py/rms-viewmaster) | [![Build status](https://img.shields.io/github/actions/workflow/status/SETI/rms-viewmaster/run-app-tests.yml?branch=main)](https://github.com/SETI/rms-viewmaster/actions) | [![Code coverage](https://img.shields.io/codecov/c/github/SETI/rms-viewmaster/main?logo=codecov)](https://codecov.io/gh/SETI/rms-viewmaster) |

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
   ```

3. Set the environment variable `PDS3_HOLDINGS_DIR` to the path of your PDS3 holdings.

4. Create the `/var/www/` (Linux) or `/Library/WebServer` (Mac) directory and set the ownership to avoid permission issues when creating logs (Note: log files are under these root directories):

   For Linux:

   ```bash
   sudo mkdir /var/www/
   sudo chown -R user /var/www/   # Replace "user" with your username
   ```

   For Mac:

   ```bash
   sudo mkdir /Library/WebServer
   sudo chown -R user /Library/WebServer   # Replace "user" with your username
   ```

Running Locally

1. Start the server at the root of the repo:

   ```bash
   python -m viewmaster.viewmaster
   ```

2. Open your browser and go to:

   <http://127.0.0.1:8080/>
   *(This corresponds to `VIEWMASTER_PREFIX_` in `viewmaster_config.py`.)*

# Contributing

Information on contributing to this package can be found in the
[Contributing Guide](https://github.com/SETI/rms-viewmaster/blob/main/CONTRIBUTING.md).

# Links
<!-- Update the readthedocs link once the branch merged into main -->
- [Documentation](https://rms-viewmaster.readthedocs.io/en/clean_up_viewmaster/)
- [Repository](https://github.com/SETI/rms-viewmaster)
- [Issue tracker](https://github.com/SETI/rms-viewmaster/issues)
<!-- Add this once we make pip install working -->
<!-- - [PyPi](https://pypi.org/project/rms-viewmaster) -->
