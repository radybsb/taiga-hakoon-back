# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from django.apps import apps
from types import SimpleNamespace

from taiga.base.filters import CanViewTasksFilterBackend


def attachment_owner_condition(queryset, request=None):
    """Read story and visible child-task files without changing their ownership."""
    model = queryset.model
    content_type = apps.get_model("contenttypes", "ContentType").objects.get_for_model(model)
    table = model._meta.db_table
    direct = f"(content_type_id = {content_type.id} AND object_id = {table}.id)"
    if model._meta.label_lower != "userstories.userstory" or request is None:
        return direct, ()

    task_model = apps.get_model("tasks", "Task")
    task_type = apps.get_model("contenttypes", "ContentType").objects.get_for_model(task_model)
    # Reuse task visibility rules, but not the story request's object/status filters.
    permission_view = SimpleNamespace(filter_fields=(), order_by_fields=())
    tasks = CanViewTasksFilterBackend().filter_queryset(request, task_model.objects.all(), permission_view)
    tasks = tasks.extra(where=[f"tasks_task.user_story_id = {table}.id",
                               f"tasks_task.project_id = {table}.project_id"])
    sql, params = tasks.order_by().values("id").query.sql_with_params()
    inherited = f"(content_type_id = {task_type.id} AND object_id IN ({sql}))"
    return f"({direct} OR {inherited})", params


def attach_total_attachments(queryset, as_field="total_attachments", request=None):
    """Attach attachment count to each object of the queryset.

    :param queryset: A Django queryset object.
    :param as_field: Attach the attachments count as an attribute with this name.

    :return: Queryset object with the additional `as_field` field.
    """
    condition, params = attachment_owner_condition(queryset, request)
    sql = f"SELECT count(*) FROM attachments_attachment WHERE {condition}"
    return queryset.extra(select={as_field: sql}, select_params=params)


def attach_basic_attachments(queryset, as_field="attachments_attr", request=None):
    """Attach basic attachments info as json column to each object of the queryset.

    :param queryset: A Django user stories queryset object.
    :param as_field: Attach the role points as an attribute with this name.

    :return: Queryset object with the additional `as_field` field.
    """

    condition, params = attachment_owner_condition(queryset, request)
    sql = f"""SELECT json_agg(row_to_json(t))
                FROM (
                    SELECT id, attached_file
                    FROM attachments_attachment
                    WHERE {condition} AND is_deprecated = False
                    ORDER BY attachments_attachment.order,
                             attachments_attachment.created_date, attachments_attachment.id
                ) t"""
    return queryset.extra(select={as_field: sql}, select_params=params)
