#
# Viewmaster Help Guide

Version 1.0

Sep, 2025

#
# Run Viewmaster
## Setup the environment (only need to do once for the 1st time running)
- Clone the rms-viewmaster repo:
    - `git clone https://github.com/SETI/rms-viewmaster.git`
- Create virtual environment and install required packages at rms-viewmaster:
    - `python -m venv myenv` (Replace `myenv` with the desired name for your virtual environment)
    - `source myenv/bin/activate`
    - `pip install -r requirements.txt`
- Create an environement variable `PDS3_HOLDINGS` to store the path of PDS3 holdings.

#
## Run viewmaster locally
- Execute viewmaster.py in the terminal:
    - `sudo -E python viewmaster/viewmaster.py`
- Open your browser and enter `http://127.0.0.1:8080/` (this is the value assigned to VIEWMASTER_PREFIX_ in viewmaster_config.py). Now the testing viewmaster will be running on your browser.
