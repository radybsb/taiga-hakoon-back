"""Authenticated Unsplash proxy: API credentials never reach the browser."""
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import requests
from django.conf import settings
from django.core.cache import cache
from django.core import signing
from taiga.base.api.viewsets import ViewSet
from taiga.base.api.permissions import IsAuthenticated, TaigaResourcePermission
from taiga.base.decorators import list_route
from taiga.base.response import Response


class BackgroundPhotoPermission(TaigaResourcePermission):
    enough_perms = IsAuthenticated()


class BackgroundPhotosViewSet(ViewSet):
    permission_classes = (BackgroundPhotoPermission,)

    def _get(self, path, params=None):
        key = getattr(settings, 'UNSPLASH_ACCESS_KEY', '')
        if not key:
            return None
        result = requests.get('https://api.unsplash.com' + path, params=params,
                              headers={'Authorization': 'Client-ID ' + key,
                                       'Accept-Version': 'v1'}, timeout=10)
        result.raise_for_status()
        return result.json()

    def list(self, request):
        query = request.QUERY_PARAMS.get('q', '').strip()[:100] or 'landscape nature'
        try:
            page = max(1, min(50, int(request.QUERY_PARAMS.get('page', 1))))
        except (TypeError, ValueError):
            return Response({'detail': 'Invalid page.'}, status=400)
        cache_key = 'background-photos-hd-v1:' + hashlib.sha256(f'{query}:{page}'.encode()).hexdigest()
        result = cache.get(cache_key)
        if result is not None:
            return Response(result)
        try:
            data = self._get('/search/photos', {'query': query, 'page': page, 'per_page': 12,
                                               'orientation': 'landscape', 'content_filter': 'high'})
            if data is None:
                return Response({'detail': 'Photo service is not configured.'}, status=503)
            photos = []
            for photo in data['results']:
                if photo.get('width', 0) < 1920 or photo.get('height', 0) < 1080:
                    continue
                source = urlsplit(photo['urls']['raw'])
                if source.scheme != 'https' or source.netloc != 'images.unsplash.com':
                    continue
                params = dict(parse_qsl(source.query))
                params.update({'w': str(min(photo['width'], 3840)), 'q': '85', 'fit': 'max', 'auto': 'format'})
                wallpaper_url = urlunsplit((source.scheme, source.netloc, source.path, urlencode(params), ''))
                download = urlsplit(photo['links']['download_location'])
                if download.scheme != 'https' or download.netloc != 'api.unsplash.com':
                    continue
                photos.append({'id': photo['id'], 'token': signing.dumps({'id': photo['id'], 'path': download.path, 'query': download.query}, salt='board-photo'), 'url': wallpaper_url,
                               'thumbnail': photo['urls']['small'],
                               'description': photo.get('alt_description') or 'Unsplash photo',
                               'author': photo['user']['name'],
                               'profile': photo['user']['links']['html'] + '?utm_source=hakoon_taiga&utm_medium=referral'})
            result = {'photos': photos, 'more': page < data['total_pages']}
            cache.set(cache_key, result, 900)
            return Response(result)
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return Response({'detail': 'Photo service is temporarily unavailable.'}, status=503)

    @list_route(methods=['POST'])
    def select(self, request):
        photo_id = request.DATA.get('id', '')
        if not isinstance(photo_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', photo_id):
            return Response({'detail': 'Invalid photo.'}, status=400)
        try:
            selected = signing.loads(request.DATA.get('token', ''), salt='board-photo', max_age=86400)
        except (signing.BadSignature, TypeError):
            return Response({'detail': 'Search for this photo again.'}, status=400)
        path = selected.get('path')
        if selected.get('id') != photo_id or path != '/photos/' + photo_id + '/download':
            return Response({'detail': 'Invalid photo.'}, status=400)
        if selected.get('query'):
            path += '?' + selected['query']
        try:
            if self._get(path) is None:
                return Response({'detail': 'Photo service is not configured.'}, status=503)
            return Response({'ok': True})
        except (requests.RequestException, ValueError):
            return Response({'detail': 'Photo could not be selected.'}, status=503)
