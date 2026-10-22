from django.conf import settings
from django.db import migrations, models


def preserve_assignees(apps, schema_editor):
    model = apps.get_model("epics", "Epic")
    for item in model.objects.using(schema_editor.connection.alias).exclude(assigned_to=None).iterator():
        item.assigned_users.add(item.assigned_to_id)


class Migration(migrations.Migration):
    dependencies = [("epics", "0006_auto_20200615_0811"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="epic", name="assigned_users",
            field=models.ManyToManyField(blank=True, related_name="assigned_epics", to=settings.AUTH_USER_MODEL, verbose_name="assigned users")),
        migrations.RunPython(preserve_assignees, migrations.RunPython.noop),
    ]
