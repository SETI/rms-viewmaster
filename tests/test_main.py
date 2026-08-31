"""Tests for the viewmaster CLI entry point."""

from unittest.mock import MagicMock, patch

from viewmaster.viewmaster import main


@patch('viewmaster.viewmaster.create_app')
def test_main_runs_dev_server_with_env_bind(mock_create_app):
    app = MagicMock()
    mock_create_app.return_value = app
    env = {
        'VIEWMASTER_HOST': '127.0.0.1',
        'VIEWMASTER_PORT': '9090',
    }
    with patch.dict('os.environ', env, clear=False):
        assert main() == 0
    app.run.assert_called_once_with(host='127.0.0.1', port=9090, debug=False)
