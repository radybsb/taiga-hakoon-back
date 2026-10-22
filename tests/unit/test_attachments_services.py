# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from unittest import mock

import pytest

from taiga.projects.attachments import services

from .. import factories as f


@pytest.mark.django_db(transaction=True)
def test_get_attachment_by_id(django_assert_num_queries):
    att, other_att = f.IssueAttachmentFactory(), f.IssueAttachmentFactory()
    assert att.content_object.project_id != other_att.content_object.project_id

    # Attachment not exist
    with django_assert_num_queries(1):
        assert services.get_attachment_by_id(other_att.content_object.project_id, 99999) is None

    # Attachment does not belong to an object of the project
    with django_assert_num_queries(2):
        assert services.get_attachment_by_id(other_att.content_object.project_id, att.id) is None

    # Attachment do belongs to the project
    with django_assert_num_queries(2):
        assert services.get_attachment_by_id(att.content_object.project_id, att.id) == att


@pytest.mark.parametrize("url, expected", [
    ("http://media.example.com/a/file.png", "http://media.example.com/a/file.png"),
    ("http://media.example.com/a/file.png?token=x", "http://media.example.com/a/file.png?token=x"),
    ("/a/file.png", None),
    ("http://www.example.com/logo.png", None),
])
def test_url_is_an_attachment(url, expected):
    assert services.url_is_an_attachment(url, base="http://media.example.com/a/") == expected


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("attachment_factory, expected", [
    (f.WikiAttachmentFactory, "wikipage"),
    (f.IssueAttachmentFactory, "issue"),
])
def test_generate_refresh_fragment(attachment_factory, expected):
    att = attachment_factory()
    frag = services.generate_refresh_fragment(att)
    assert "{}={}:{}".format(services.REFRESH_PARAM, expected, att.id) == frag


@pytest.mark.parametrize("url, expected", [
    ("http://static.test/a/file.png", (False, False)),
    ("http://static.test/a/file.png?token=x", (False, False)),
    ("http://static.test/a/file.png?token=x#spurious", (False, False)),
    ("http://static.test/a/file.png?token=x#" + services.REFRESH_PARAM, (False, False)),
    ("http://static.test/a/file.png?token=x#" + services.REFRESH_PARAM + "=xxx", (False, False)),
    ("http://static.test/a/file.png?token=x#" + services.REFRESH_PARAM + "=us:42", ("us", 42)),
])
def test_render_attachment_extract_refresh_id(url, expected):
    assert services.extract_refresh_id(url) == expected


@pytest.mark.parametrize("attachment, expected", [
    (mock.MagicMock(id=42), services.REFRESH_PARAM + "=us:42"),
])
def test_generate_refresh_fragment_with_type(attachment, expected):
    assert services.generate_refresh_fragment(attachment, "us") == expected


@pytest.mark.parametrize("name", ["attachments/animated.gif", "attachments/ANIMATED.GIF"])
def test_card_gif_uses_original_storage_url(name):
    with mock.patch.object(services, "default_storage") as storage, \
         mock.patch.object(services, "get_thumbnail_url") as thumbnail, \
         mock.patch.object(services, "get_absolute_url", side_effect=lambda url: url):
        storage.url.return_value = "https://media.example.com/animated.gif?token=signed"
        assert services.get_card_image_url(name) == storage.url.return_value
        storage.url.assert_called_once_with(name)
        thumbnail.assert_not_called()


def test_card_gif_field_file_keeps_signed_url():
    file = mock.Mock(name="file")
    file.name = "attachments/animated.gif"
    file.url = "https://media.example.com/animated.gif?token=signed"
    with mock.patch.object(services, "get_absolute_url", side_effect=lambda url: url):
        assert services.get_card_image_thumbnail_url(mock.Mock(attached_file=file)) == file.url


def test_card_static_image_still_uses_thumbnail():
    with mock.patch.object(services, "get_thumbnail_url", return_value="thumbnail.png") as thumbnail:
        assert services.get_card_image_url("attachments/photo.jpg") == "thumbnail.png"
        thumbnail.assert_called_once_with("attachments/photo.jpg", services.settings.THN_ATTACHMENT_CARD)
    assert services.get_card_image_url(None) is None


def test_card_board_serializer_preserves_gif_url():
    from types import SimpleNamespace
    from taiga.projects.attachments.serializers import BasicAttachmentsInfoSerializerMixin

    obj = SimpleNamespace(include_attachments=True, attachments_attr=[
        {"id": 1, "attached_file": "attachments/animated.gif"},
        {"id": 2, "attached_file": "attachments/photo.jpg"},
    ])
    with mock.patch.object(services, "default_storage") as storage, \
         mock.patch.object(services, "get_thumbnail_url", return_value="thumbnail.png"):
        storage.url.return_value = "https://media.example.com/animated.gif?token=signed"
        result = BasicAttachmentsInfoSerializerMixin().get_attachments(obj)
    assert result[0]["thumbnail_card_url"] == storage.url.return_value
    assert result[1]["thumbnail_card_url"] == "thumbnail.png"
