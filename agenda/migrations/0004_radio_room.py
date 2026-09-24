from django.db import migrations


def rename(apps, schema_editor):
    apps.get_model('agenda', 'Resource').objects.using(schema_editor.connection.alias).filter(key='sala-grande').update(name='Sala de reunião 2 - corredor rádio (acima de 8 pessoas)')


class Migration(migrations.Migration):
    dependencies = [('agenda', '0003_room_names')]
    operations = [migrations.RunPython(rename, migrations.RunPython.noop)]
