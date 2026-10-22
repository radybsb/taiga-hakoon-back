from types import SimpleNamespace
from unittest.mock import patch
from django.core.cache import cache
from django.test import override_settings
from taiga.backgrounds import BackgroundPhotosViewSet


def test_photo_search_and_signed_download():
    cache.clear()
    photo = {'id': 'test-photo', 'width': 6000, 'height': 4000, 'links': {'download_location': 'https://api.unsplash.com/photos/test-photo/download?ixid=test'},
             'urls': {'raw': 'https://images.unsplash.com/photo-test?ixid=tracking', 'regular': 'https://images.unsplash.com/photo-test', 'small': 'https://images.unsplash.com/photo-test?w=200'},
             'user': {'name': 'Photographer', 'links': {'html': 'https://unsplash.com/@photographer'}}}
    view = BackgroundPhotosViewSet()
    with patch.object(view, '_get', return_value={'results': [dict(photo, id='small', width=1280, height=720), dict(photo, id='short', width=4000, height=900), photo], 'total_pages': 2}):
        result = view.list(SimpleNamespace(QUERY_PARAMS={'q': 'mountains'}))
    assert result.status_code == 200
    entry = result.data['photos'][0]
    assert len(result.data['photos']) == 1
    assert 'w=3840' in entry['url']
    assert 'ixid=tracking' in entry['url']
    assert 'q=85' in entry['url']
    assert 'utm_source=' in entry['profile']
    assert result.data['more']
    with patch.object(view, '_get', return_value={}) as get:
        result = view.select(SimpleNamespace(DATA={'id': entry['id'], 'token': entry['token']}))
        assert result.status_code == 200
        get.assert_called_once_with('/photos/test-photo/download?ixid=test')
    assert view.select(SimpleNamespace(DATA={'id': entry['id'], 'token': 'tampered'})).status_code == 400
    assert view.select(SimpleNamespace(DATA={'id': '../bad'})).status_code == 400


@override_settings(UNSPLASH_ACCESS_KEY='')
def test_photos_unavailable_without_credentials():
    cache.clear()
    result = BackgroundPhotosViewSet().list(SimpleNamespace(QUERY_PARAMS={}))
    assert result.status_code == 503
