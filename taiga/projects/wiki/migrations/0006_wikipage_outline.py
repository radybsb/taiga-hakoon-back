from django.db import migrations
from taiga.base.db.models.fields import JSONField


def populate_outlines(apps, schema_editor):
    # This parser only depends on Markdown and the standard library; it does not
    # load live Django models or call save(), preserving versions and history.
    from taiga.projects.wiki.outline import build_outline
    Page = apps.get_model("wiki", "WikiPage")
    for page in Page.objects.using(schema_editor.connection.alias).only("id", "content").iterator(chunk_size=500):
        Page.objects.using(schema_editor.connection.alias).filter(pk=page.pk).update(outline=build_outline(page.content))


class Migration(migrations.Migration):
    dependencies = [("wiki", "0005_auto_20161201_1628")]
    operations = [
        migrations.AddField(model_name="wikipage", name="outline", field=JSONField(default=list, blank=True, editable=False)),
        migrations.RunPython(populate_outlines, migrations.RunPython.noop),
    ]
