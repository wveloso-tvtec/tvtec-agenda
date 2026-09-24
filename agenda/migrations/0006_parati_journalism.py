from django.db import migrations


def rename(apps, schema_editor):
    resources = apps.get_model('agenda', 'Resource').objects.using(schema_editor.connection.alias)
    resources.filter(key='parati').update(name='Parati (exclusivo jornalismo)')


def reverse(apps, schema_editor):
    resources = apps.get_model('agenda', 'Resource').objects.using(schema_editor.connection.alias)
    resources.filter(key='parati', name='Parati (exclusivo jornalismo)').update(name='Parati')


class Migration(migrations.Migration):
    dependencies = [('agenda', '0005_booking_email')]
    operations = [migrations.RunPython(rename, reverse)]
