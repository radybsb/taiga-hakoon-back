"""Project taskboard configuration and task-driven story transitions."""
from django.db import transaction
from taiga.base.exceptions import ValidationError


def validate_options(options, project):
    if not isinstance(options, dict):
        raise ValidationError("Taskboard options must be an object.")
    allowed = {"story_filters", "automatic_status", "closed_task_statuses",
               "closed_story_status", "opened_story_status"}
    if set(options) - allowed:
        raise ValidationError("Unknown taskboard option.")
    for key in ("story_filters", "automatic_status"):
        if key in options and type(options[key]) is not bool:
            raise ValidationError("Taskboard flags must be booleans.")
    ids = options.get("closed_task_statuses", [])
    if not isinstance(ids, list) or any(type(pk) is not int for pk in ids):
        raise ValidationError("Choose valid closed task statuses.")
    if ids and (not project or project.task_statuses.filter(
            pk__in=ids, is_closed=True).count() != len(set(ids))):
        raise ValidationError("Choose closed task statuses from this project.")
    for key, closed in (("closed_story_status", True), ("opened_story_status", False)):
        pk = options.get(key)
        if pk is not None and (type(pk) is not int or not project or not
                project.us_statuses.filter(pk=pk, is_closed=closed).exists()):
            raise ValidationError("Choose a story status with the correct closed/open state from this project.")
    if options.get("automatic_status") and (not ids or not
            options.get("closed_story_status") or not options.get("opened_story_status")):
        raise ValidationError("Select closed task statuses and both story statuses before enabling automatic updates.")


def update_story_status(story_id):
    from taiga.projects.userstories.models import UserStory
    from taiga.projects.history.services import take_snapshot

    with transaction.atomic():
        story = UserStory.objects.select_for_update(of=("self",)).select_related("project", "status").filter(pk=story_id).first()
        if story is None:
            return
        options = story.project.taskboard_options or {}
        if not options.get("automatic_status"):
            return
        # Deleted/reclassified statuses disable transitions until settings are repaired.
        try:
            validate_options(options, story.project)
        except ValidationError:
            return
        statuses = list(story.tasks.values_list("status_id", flat=True))
        if not statuses:
            return
        complete = all(pk in options["closed_task_statuses"] for pk in statuses)
        if complete:
            target = options["closed_story_status"]
        elif story.status and story.status.is_closed:
            target = options["opened_story_status"]
        else:
            return
        if story.status_id != target:
            story.status_id = target
            story.version += 1
            story.save(update_fields=["status", "version", "modified_date"])
            take_snapshot(story, comment="Automatic user story status update")
