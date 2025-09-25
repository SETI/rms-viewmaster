#
# Viewmaster Help Guide

Version 1.0

Sep, 2025

#
# Run Viewmaster
## Setup the environment (only need to do once for the 1st time running)
- Create virtual environment and install required packages at rms-viewmaster:
    - `python -m venv myenv` (Replace `myenv` with the desired name for your virtual environment)
    - `pip isntall -r requirements.txt`
- Create /Library/Webserver/Documents:
    - `sudo mkdir -p /Library/Webserver/Documents`
- Create a symlink to the holdings directory under /Library/Webserver/Documents:
    - `sudo ln -s "my_holdings" /Library/WebServer/Documents/holdings` (Replace `my_holdings` with the desired holdings path)
- Install Apache and put holdings path in the customized httpd configuration file (viewmaster.py will look for HOLDINGS_PATHS in httpd_customization.conf):
    - `brew install httpd`
    - `echo 'Define HOLDINGS_PATHS "my_holdings"' > /opt/homebrew/etc/httpd/httpd_customization.conf` (Replace `my_holdings` with the desired holdings path)

#
## Run viewmaster locally
- Execute viewmaster.py in the terminal:
    - `sudo python viewmaster/viewmaster.py`
- Open your browser and enter `http://127.0.0.1:8080/` (this is the value assigned to VIEWMASTER_PREFIX_ in viewmaster_config.py). Now the testing viewmaster will be running on your browser.
