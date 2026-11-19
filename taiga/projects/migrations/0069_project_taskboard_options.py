from django.db import migrations
from taiga.base.db.models.fields import JSONField


class Migration(migrations.Migration):
    dependencies = [("projects", "0068_project_archived_code")]
    operations = [migrations.AddField(
        model_name="project", name="taskboard_options",
        field=JSONField(default=dict, blank=True),
    )]
