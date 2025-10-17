| PyPI Release | Test Status | Code Coverage |
| ------------- | ------------ | -------------- |
| [![PyPI version](https://badge.fury.io/py/rms-viewmaster.svg)](https://badge.fury.io/py/rms-viewmaster) | [![Build status](https://img.shields.io/github/actions/workflow/status/SETI/rms-viewmaster/run-app-tests.yml?branch=main)](https://github.com/SETI/rms-viewmaster/actions) | [![Code coverage](https://img.shields.io/codecov/c/github/SETI/rms-viewmaster/main?logo=codecov)](https://codecov.io/gh/SETI/rms-viewmaster) |

# 🚀 Viewmaster

## 🧭 Overview

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
