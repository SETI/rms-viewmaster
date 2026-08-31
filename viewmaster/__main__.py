"""Allow ``python -m viewmaster`` to start the local development server."""

import os

# Set before importing viewmaster.viewmaster so viewmaster_config sees it.
os.environ.setdefault('VIEWMASTER_TESTING', '1')

from viewmaster.viewmaster import main

if __name__ == '__main__':
    main()
