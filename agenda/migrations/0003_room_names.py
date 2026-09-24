from django.db import migrations


ROOMS = (
    ('sala-pequena', 'Sala pequena', 'Sala de reunião 1 - corredor principal (até 4 pessoas)'),
    ('sala-grande', 'Sala grande', 'Sala de reunião 2 (acima de 8 pessoas)'),
)


def rename(apps, schema_editor):
    resources = apps.get_model('agenda', 'Resource').objects.using(schema_editor.connection.alias)
    for key, old, new in ROOMS:
        resources.filter(key=key).update(name=new)


def reverse(apps, schema_editor):
    resources = apps.get_model('agenda', 'Resource').objects.using(schema_editor.connection.alias)
    for key, old, new in ROOMS:
        resources.filter(key=key, name=new).update(name=old)


class Migration(migrations.Migration):
    dependencies = [('agenda', '0002_integrity_and_resources')]
    operations = [migrations.RunPython(rename, reverse)]
