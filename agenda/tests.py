import hashlib, json, secrets, threading, tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from django.test import TestCase, TransactionTestCase, Client, override_settings
from django.db import transaction, IntegrityError, connections, close_old_connections
from django.utils import timezone
from django.core import mail
from django.core.management import call_command
from .models import *
from .services import *

def person(email='teste@example.test',role='collaborator',**kw):
    return User.objects.create_user(username=email,email=email,password='Teste-Local-2026!#',first_name='Usuário de teste',role=role,is_active=True,verified=True,rooms=True,vehicles=True,**kw)

class Rules(TestCase):
    def setUp(self):
        self.u=person();self.admin=person('admin@example.test','admin');self.other=person('outro@example.test')
        self.room=Resource.objects.get(key='sala-pequena');self.car=Resource.objects.get(key='gol')
        self.day=(timezone.now().astimezone(TZ)+timedelta(days=10)).date().isoformat()
    def payload(self,resource=None,start='09:00',end='10:00',**kw):
        return {'resource':(resource or self.room).id,'start':self.day+'T'+start,'end':self.day+'T'+end,'title':'Finalidade privada','notes':'Observação privada','destination':'Destino privado','driver':'Condutor privado','request_key':secrets.token_hex(16),**kw}
    def save(self,**kw): return save_occupancy(self.u,self.payload(**kw))
    def post(self,client,action,payload): return client.post('/api/'+action,json.dumps(payload),content_type='application/json')
    def test_authorization_by_resource_and_profile(self):
        self.u.vehicles=False;self.u.save()
        with self.assertRaises(Problem): self.save(resource=self.car)
        with self.assertRaises(Problem): save_resource(self.u,{'id':self.room.id})
        with self.assertRaises(Problem): self.save(kind='block')
        self.assertTrue(self.save().pk)
    def test_cannot_edit_or_cancel_others(self):
        o=self.save();d=self.payload(id=o.id,updated=o.updated.isoformat())
        with self.assertRaises(Problem): save_occupancy(self.other,d)
        with self.assertRaises(Problem): cancel_occupancy(self.other,{'id':o.id})
    def test_disabled_user_existing_session_and_stale_object(self):
        c=Client();c.force_login(self.u)
        User.objects.filter(pk=self.u.pk).update(is_active=False)
        self.assertEqual(c.get('/api/resources').status_code,401)
        with self.assertRaises(Problem): self.save()
    def test_last_admin_protected(self):
        data={'id':self.admin.id,'name':'Admin','role':'collaborator','active':True}
        with self.assertRaises(Problem): update_user(self.admin,data)
        self.admin.refresh_from_db();self.assertEqual(self.admin.role,'admin')
    def test_overlap_adjacent_and_different_resources(self):
        self.save()
        with self.assertRaises(Problem): self.save(start='09:30',end='10:30')
        self.assertTrue(self.save(start='10:00',end='10:30').pk)
        self.assertTrue(self.save(resource=self.car).pk)
    def test_database_overlap_insert_and_update(self):
        self.save();o=self.save(start='11:00',end='12:00')
        with self.assertRaises(IntegrityError),transaction.atomic():
            Occupancy.objects.filter(pk=o.pk).update(start=local_datetime(self.day+'T09:30'))
        with self.assertRaises(IntegrityError),transaction.atomic():
            Occupancy.objects.create(resource=self.room,owner=self.admin,start=local_datetime(self.day+'T09:00'),end=local_datetime(self.day+'T10:00'),title='Direto',request_key='direct',fingerprint='x',kind='block')
    def test_blocks_share_conflict_rule(self):
        save_occupancy(self.admin,self.payload(kind='block'))
        with self.assertRaises(Problem): self.save()
    def test_cancel_releases_availability_preserves_record(self):
        o=self.save();cancel_occupancy(self.u,{'id':o.id});self.assertTrue(self.save().pk)
        o.refresh_from_db();self.assertTrue(o.cancelled);self.assertTrue(Audit.objects.filter(entity=f'ocupacao:{o.id}').exists())
    def test_edit_validates_conflicts(self):
        self.save();o=self.save(start='11:00',end='12:00')
        with self.assertRaises(Problem): save_occupancy(self.u,self.payload(id=o.id,updated=o.updated.isoformat()))
    def test_optimistic_edit_prevents_lost_update(self):
        o=self.save()
        with self.assertRaises(Problem): save_occupancy(self.u,self.payload(id=o.id,updated='old'))
    def test_room_limits(self):
        for start,end in [('05:30','06:30'),('09:00','09:00'),('09:00','09:15'),('09:15','10:00'),('23:30','23:59')]:
            with self.subTest(start=start,end=end),self.assertRaises(Problem): self.save(start=start,end=end)
        self.assertTrue(self.save(start='06:00',end='06:30').pk)
        self.assertTrue(self.save(start='23:00',end='23:59').pk)
        tomorrow=(local_datetime(self.day+'T00:00')+timedelta(days=1)).date().isoformat()
        with self.assertRaises(Problem): save_occupancy(self.u,{**self.payload(start='22:00'),'end':tomorrow+'T00:00'})
    def test_vehicle_overnight_and_all_day(self):
        tomorrow=(local_datetime(self.day+'T00:00')+timedelta(days=1)).date().isoformat()
        d=self.payload(self.car,start='23:30');d['end']=tomorrow+'T01:00';o=save_occupancy(self.u,d)
        self.assertEqual((o.end-o.start).total_seconds(),5400)
        cancel_occupancy(self.u,{'id':o.id})
        d=self.payload(self.car,start='00:00',mode='day');d['end']=tomorrow+'T00:00';o=save_occupancy(self.u,d)
        self.assertEqual(o.start.astimezone(ZoneInfo('UTC')).hour,3)
        self.assertEqual((o.end-o.start).total_seconds(),86400)
        with self.assertRaises(Problem): self.save(resource=self.car)
    def test_all_day_conflicts_with_partial_occupancy(self):
        self.save(resource=self.car)
        d=self.payload(self.car,start='00:00',mode='day');d['end']=(local_datetime(self.day+'T00:00')+timedelta(days=1)).isoformat()
        with self.assertRaises(Problem): save_occupancy(self.u,d)
    def test_privacy_at_api_response(self):
        o=self.save();c=Client();c.force_login(self.other)
        data=c.get('/api/occupancies',{'start':self.day+'T00:00','end':self.day+'T23:59'}).json()['occupancies'][0]
        for k in ('title','notes','destination','driver','mode'): self.assertNotIn(k,data)
        self.assertEqual(data['responsible'],self.u.first_name)
        self.assertIn('title',occupancy_data(o,self.u));self.assertIn('title',occupancy_data(o,self.admin))
    def test_shared_all_day_label_preserves_private_details(self):
        data=self.payload(self.car,start='00:00',mode='day')
        data['end']=(local_datetime(self.day+'T00:00')+timedelta(days=1)).isoformat()
        save_occupancy(self.u,data)
        client=Client();client.force_login(self.other)
        public=client.get('/api/occupancies',{'start':self.day+'T00:00','end':self.day+'T23:59'}).json()['occupancies'][0]
        self.assertTrue(public['all_day'])
        self.assertEqual(public['responsible'],self.u.first_name)
        for field in ('title','notes','destination','driver','mode'):
            self.assertNotIn(field,public)

    def test_idempotency_same_payload_and_conflicting_payload(self):
        d=self.payload();a=save_occupancy(self.u,d);b=save_occupancy(self.u,d);self.assertEqual(a.pk,b.pk)
        with self.assertRaises(Problem): save_occupancy(self.u,{**d,'title':'Diferente'})
    def test_past_new_rejected_admin_adjustment_allowed_with_reason(self):
        o=self.save();past=timezone.now()-timedelta(days=3)
        start=past.astimezone(TZ).replace(hour=9,minute=0,second=0,microsecond=0);end=start+timedelta(hours=1)
        with self.assertRaises(Problem): save_occupancy(self.admin,{**self.payload(),'start':start.isoformat(),'end':end.isoformat()})
        Occupancy.objects.filter(pk=o.pk).update(start=start,end=end);o.refresh_from_db()
        d={**self.payload(),'id':o.pk,'updated':o.updated.isoformat(),'start':start.isoformat(),'end':(end+timedelta(minutes=30)).isoformat()}
        with self.assertRaises(Problem): save_occupancy(self.admin,d)
        d['reason']='Correção documentada';self.assertEqual(save_occupancy(self.admin,d).end,end+timedelta(minutes=30))
    def test_deactivation_requires_explicit_resolution(self):
        o=self.save();d={'id':self.u.id,'name':'Usuário de teste','active':False}
        with self.assertRaises(Problem) as e: update_user(self.admin,d)
        self.assertEqual(e.exception.extra['affected'][0]['id'],o.id)
        update_user(self.admin,{**d,'reservations':'cancel','affected':[o.id]});o.refresh_from_db();self.assertTrue(o.cancelled)
    def test_resource_change_rejects_affected_reservations(self):
        self.save();d={**resource_data(self.room),'active':False}
        with self.assertRaises(Problem): save_resource(self.admin,d)
        self.room.refresh_from_db();self.assertTrue(self.room.active)
    def test_periods_not_invented_and_configured_period_validates(self):
        with self.assertRaises(Problem): self.save(resource=self.car,mode='period',period='morning')
        save_resource(self.admin,{**resource_data(self.car),'periods':{'morning':[540,600]}})
        self.assertTrue(self.save(resource=self.car,mode='period',period='morning').pk)
    def test_csrf_required(self):
        c=Client(enforce_csrf_checks=True);c.force_login(self.u)
        self.assertEqual(self.post(c,'save',self.payload()).status_code,403)
    def test_auth_required(self): self.assertEqual(Client().get('/api/resources').status_code,401)
    def test_throttle(self):
        for i in range(10):self.assertTrue(throttle('test'))
        self.assertFalse(throttle('test'))
    def test_no_public_registration_or_role_elevation(self):
        c=Client();c.force_login(self.u)
        self.assertEqual(self.post(c,'update-user',{'id':self.u.id,'role':'admin'}).status_code,403)
        self.assertEqual(self.post(Client(),'register',{'email':'x@x.com'}).status_code,401)
    def test_seed_is_idempotent(self):
        from importlib import import_module
        from django.apps import apps
        import_module('agenda.migrations.0002_integrity_and_resources').seed(apps,None)
        self.assertEqual(Resource.objects.count(),5)
    def test_existing_session_invalid_after_password_reset(self):
        c=Client();c.force_login(self.u)
        self.u.set_password('Different-password!123');self.u.save()
        self.assertEqual(c.get('/api/resources').status_code,401)
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',EMAIL_HOST='test',DEFAULT_FROM_EMAIL='agenda@example.test',MAIL_MODE='smtp')
    def test_invitation_verification_password_and_single_use(self):
        u=invite_user(self.admin,{'name':'Convidado de teste','email':'new@example.test','rooms':True,'vehicles':False})
        self.assertFalse(u.is_active);self.assertFalse(u.has_usable_password())
        import re
        token=re.search(r'token=([^\s]+)',mail.outbox[-1].body).group(1)
        self.assertFalse(Invitation.objects.filter(digest=token).exists())
        c=Client();response=self.post(c,'activate',{'token':token,'password':'Outra-Frase-Segura!2026'})
        self.assertEqual(response.status_code,200,response.content)
        u.refresh_from_db();self.assertTrue(u.verified);self.assertTrue(u.check_password('Outra-Frase-Segura!2026'))
        self.assertEqual(self.post(c,'activate',{'token':token,'password':'Outra-Frase-Segura!2026'}).status_code,410)
    def test_expired_invitation(self):
        Invitation.objects.create(user=self.u,digest=hashlib.sha256(b'token').hexdigest(),expires=timezone.now()-timedelta(seconds=1))
        self.assertEqual(Client().get('/api/token',{'token':'token'}).status_code,410)
    def test_read_persisted_reservation_with_new_session(self):
        c=Client();c.force_login(self.u);response=self.post(c,'save',self.payload());self.assertEqual(response.status_code,200)
        c2=Client();c2.force_login(self.u);self.assertEqual(len(c2.get('/api/mine').json()['occupancies']),1)
    def test_overview_includes_next_booking_beyond_thirty_days(self):
        start=local_datetime(self.day+'T09:00')+timedelta(days=90)
        save_occupancy(self.u,{**self.payload(),'start':start.isoformat(),'end':(start+timedelta(minutes=30)).isoformat()})
        c=Client();c.force_login(self.other)
        items=c.get('/api/overview').json()['occupancies']
        self.assertEqual(len(items),1);self.assertNotIn('notes',items[0])
    def test_stale_admin_permissions_rechecked_in_transaction(self):
        User.objects.filter(pk=self.admin.pk).update(role='collaborator')
        with self.assertRaises(Problem): save_resource(self.admin,resource_data(self.room))
    def test_disabled_resource_rejects_new_booking(self):
        self.room.active=False;self.room.save()
        with self.assertRaises(Problem):self.save()
    def test_naive_times_use_institution_timezone(self):
        dt=local_datetime(self.day+'T09:00')
        self.assertEqual(dt.astimezone(ZoneInfo('UTC')).hour,12)
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',EMAIL_HOST='test',DEFAULT_FROM_EMAIL='agenda@example.test',MAIL_MODE='smtp')
    def test_password_recovery_and_session_revocation(self):
        import re
        c=Client();c.force_login(self.u)
        anonymous=Client();response=self.post(anonymous,'recover',{'email':self.u.email})
        self.assertEqual(response.status_code,200)
        token=re.search(r'token=([^\s]+)',mail.outbox[-1].body).group(1)
        response=self.post(anonymous,'activate',{'token':token,'password':'Senha-Redefinida!29874'})
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(c.get('/api/resources').status_code,401)
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',EMAIL_HOST='test',DEFAULT_FROM_EMAIL='agenda@example.test',MAIL_MODE='smtp')
    def test_provision_admin_never_activates_without_verification(self):
        from io import StringIO
        call_command('provision_admin',stdout=StringIO())
        u=User.objects.get(email='wveloso@tvtecjundiai.com.br')
        self.assertEqual(u.role,'admin');self.assertFalse(u.is_active);self.assertFalse(u.verified);self.assertFalse(u.has_usable_password())
        self.assertEqual(mail.outbox[-1].to,['wveloso@tvtecjundiai.com.br'])

class RealConcurrency(TransactionTestCase):
    # Dedicated on-disk SQLite database and independent connections: this is not a mocked race.
    def test_two_independent_process_style_connections(self):
        import sqlite3
        from importlib import import_module
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'race.sqlite3'
            db=sqlite3.connect(path)
            db.execute('CREATE TABLE agenda_occupancy(id INTEGER PRIMARY KEY, resource_id INTEGER, start TEXT, end TEXT, cancelled INTEGER)')
            class Schema:
                def execute(self,sql): db.execute(sql)
            import_module('agenda.migrations.0002_integrity_and_resources').triggers(None,Schema())
            db.commit();db.close();barrier=threading.Barrier(2)
            def attempt():
                connection=sqlite3.connect(path,timeout=10)
                barrier.wait()
                try:
                    connection.execute('BEGIN IMMEDIATE')
                    connection.execute("INSERT INTO agenda_occupancy(resource_id,start,end,cancelled) VALUES(1,'2030-01-01 12:00','2030-01-01 13:00',0)")
                    connection.commit();return 'saved'
                except sqlite3.IntegrityError:
                    connection.rollback();return 'conflict'
                finally:connection.close()
            with ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(lambda _:attempt(),range(2)))
            self.assertCountEqual(result,['saved','conflict'])
            db=sqlite3.connect(path);self.assertEqual(db.execute('SELECT COUNT(*) FROM agenda_occupancy').fetchone()[0],1);db.close()
