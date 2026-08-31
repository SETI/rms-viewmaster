"""Tests for Link service file resolution via PDS3_HOLDINGS_DIR."""

import os
from unittest.mock import MagicMock, patch

from viewmaster.link import create_app
from viewmaster.viewmaster_config import VIEWMASTER_PREFIX_, WEBSITE_HTTP_HOME


def _client():
    app = create_app()
    app.config['TESTING'] = True
    return app.test_client()


@patch('viewmaster.link.get_or_create_logger', return_value=MagicMock())
def test_directory_redirects_to_viewmaster(mock_logger):
    response = _client().get('/volumes/COISS_2001', follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'] == VIEWMASTER_PREFIX_ + 'volumes/COISS_2001'


@patch('viewmaster.link.get_or_create_logger', return_value=MagicMock())
def test_file_found_redirects_to_holdings_url(mock_logger, tmp_path):
    holdings = tmp_path / 'holdings'
    rel = 'volumes/COISS_2001/DATA/foo.lbl'
    dest = holdings / rel
    dest.parent.mkdir(parents=True)
    dest.write_text('label')

    with patch.dict(os.environ, {'PDS3_HOLDINGS_DIR': str(holdings)}):
        response = _client().get('/' + rel, follow_redirects=False)

    assert response.status_code == 302
    assert response.headers['Location'] == WEBSITE_HTTP_HOME + '/holdings/' + rel


@patch('viewmaster.link.get_or_create_logger', return_value=MagicMock())
def test_file_missing_returns_404(mock_logger, tmp_path):
    holdings = tmp_path / 'holdings'
    holdings.mkdir()

    with patch.dict(os.environ, {'PDS3_HOLDINGS_DIR': str(holdings)}):
        response = _client().get('/volumes/missing.lbl', follow_redirects=False)

    assert response.status_code == 404


@patch('viewmaster.link.get_or_create_logger', return_value=MagicMock())
def test_unset_holdings_dir_returns_404(mock_logger):
    env = os.environ.copy()
    env.pop('PDS3_HOLDINGS_DIR', None)
    with patch.dict(os.environ, env, clear=True):
        response = _client().get('/volumes/foo.lbl', follow_redirects=False)

    assert response.status_code == 404


@patch('viewmaster.link.get_or_create_logger', return_value=MagicMock())
def test_does_not_glob_document_root_holdings(mock_logger, tmp_path):
    """A file under a holdings* sibling of DOCUMENT_ROOT_ is not discovered."""
    holdings = tmp_path / 'holdings'
    holdings.mkdir()
    decoy = tmp_path / 'documents' / 'holdings-extra' / 'volumes'
    decoy.mkdir(parents=True)
    (decoy / 'decoy.lbl').write_text('label')

    with patch.dict(os.environ, {'PDS3_HOLDINGS_DIR': str(holdings)}):
        response = _client().get('/volumes/decoy.lbl', follow_redirects=False)

    assert response.status_code == 404
