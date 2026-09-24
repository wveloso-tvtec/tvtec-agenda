from django.db import migrations


def rename(apps, schema_editor):
    resources = apps.get_model('agenda', 'Resource').objects.using(schema_editor.connection.alias)
    resources.filter(key='gol').update(name='Gol (exclusivo jornalismo)')


def reverse(apps, schema_editor):
    resources = apps.get_model('agenda', 'Resource').objects.using(schema_editor.connection.alias)
    resources.filter(key='gol', name='Gol (exclusivo jornalismo)').update(name='Gol')


class Migration(migrations.Migration):
    dependencies = [('agenda', '0006_parati_journalism')]
    operations = [migrations.RunPython(rename, reverse)]
