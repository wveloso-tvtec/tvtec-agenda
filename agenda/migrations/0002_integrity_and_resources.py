from django.db import migrations

def seed(apps,schema_editor):
    R=apps.get_model('agenda','Resource')
    for key,name,kind in [('sala-pequena','Sala pequena','room'),('sala-grande','Sala grande','room'),('gol','Gol','vehicle'),('parati','Parati','vehicle'),('spin','Spin','vehicle')]:
        R.objects.get_or_create(key=key,defaults={'name':name,'kind':kind,'opens':360 if kind=='room' else 0,'closes':1439 if kind=='room' else 1440})
    apps.get_model('agenda','Settings').objects.get_or_create(pk=1)

def triggers(apps,schema_editor):
    # Database protection covers all writers, including concurrent connections and direct SQL.
    vendor=getattr(getattr(schema_editor,'connection',None),'vendor','sqlite')
    if vendor == 'postgresql':
        schema_editor.execute('CREATE EXTENSION IF NOT EXISTS btree_gist')
        schema_editor.execute("""ALTER TABLE agenda_occupancy ADD CONSTRAINT occupancy_no_overlap
            EXCLUDE USING gist (resource_id WITH =, tstzrange("start", "end", '[)') WITH &&)
            WHERE (cancelled = false)""")
        return
    for operation in ('INSERT','UPDATE'):
        schema_editor.execute(f'''CREATE TRIGGER occupancy_no_overlap_{operation.lower()}
        BEFORE {operation} ON agenda_occupancy WHEN NEW.cancelled = 0
        BEGIN
          SELECT RAISE(ABORT, 'occupancy_overlap') WHERE EXISTS (
            SELECT 1 FROM agenda_occupancy o
            WHERE o.resource_id = NEW.resource_id AND o.cancelled = 0
            AND o.id != COALESCE(NEW.id, -1)
            AND o.start < NEW.end AND o.end > NEW.start
          );
        END''')

def drop(apps,schema_editor):
    vendor=getattr(getattr(schema_editor,'connection',None),'vendor','sqlite')
    if vendor == 'postgresql':
        schema_editor.execute('ALTER TABLE agenda_occupancy DROP CONSTRAINT IF EXISTS occupancy_no_overlap')
        return
    for op in ('insert','update'): schema_editor.execute(f'DROP TRIGGER IF EXISTS occupancy_no_overlap_{op}')

class Migration(migrations.Migration):
    dependencies=[('agenda','0001_initial')]
    operations=[migrations.RunPython(seed,migrations.RunPython.noop),migrations.RunPython(triggers,drop)]
