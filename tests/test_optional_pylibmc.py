"""Tests that page caching works when pylibmc is not installed."""

from unittest.mock import MagicMock, patch

from viewmaster import viewmaster as vm


@patch('viewmaster.viewmaster.pdsfile.cache_lifetime', 3600, create=True)
@patch('viewmaster.viewmaster.pdscache.DictionaryCache', return_value=MagicMock(name='dict-cache'))
@patch('viewmaster.viewmaster.PAGE_CACHE', None)
@patch('viewmaster.viewmaster.PAGE_CACHING', True)
@patch('viewmaster.viewmaster.VIEWMASTER_MEMCACHE_PORT', '/tmp/memcached.socket')
@patch('viewmaster.viewmaster.pylibmc', None)
def test_get_page_cache_without_pylibmc_uses_dictionary(mock_dict_cache):
    logger = MagicMock()
    cache = vm.get_page_cache(logger)
    assert cache is mock_dict_cache.return_value
    logger.warning.assert_called()
    assert 'pylibmc' in logger.warning.call_args[0][0]
    logger.info.assert_any_call('Using DictionaryCache for page caching')
    mock_dict_cache.assert_called_once()
