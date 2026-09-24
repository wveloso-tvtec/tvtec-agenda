from unittest.mock import patch
from datetime import timedelta
from django.test import TestCase, override_settings
from django.core import mail
from django.db import transaction
from django.utils import timezone
from .models import BookingEmail, Resource, Occupancy
from .services import save_occupancy, TZ, Problem
from .tests import person
from .notifications import deliver_safely


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DEFAULT_FROM_EMAIL='agenda@example.test', MAIL_MODE='smtp')
class BookingNotifications(TestCase):
    def setUp(self):
        self.user = person()
        self.resource = Resource.objects.get(key='gol')
        start=(timezone.now().astimezone(TZ)+timedelta(days=5)).replace(hour=0,minute=0,second=0,microsecond=0)
        self.data=dict(resource=self.resource.pk,start=start.isoformat(),end=(start+timedelta(days=1)).isoformat(),mode='day',title='Visita',driver='Condutor Teste',destination='Destino',request_key='email-test')

    def test_commit_sends_once_to_owner(self):
        with self.captureOnCommitCallbacks(execute=True):
            booking=save_occupancy(self.user,self.data)
            save_occupancy(self.user,self.data)
            self.assertEqual(len(mail.outbox),0)
        self.assertEqual(len(mail.outbox),1)
        self.assertEqual(mail.outbox[0].to,[self.user.email])
        self.assertIn('Reservado o dia todo',mail.outbox[0].body)
        self.assertIn('Horário de Brasília',mail.outbox[0].body)
        item=BookingEmail.objects.get(occupancy=booking)
        self.assertIsNotNone(item.sent_at)
        deliver_safely(item.pk)
        self.assertEqual(len(mail.outbox),1)

    def test_failure_keeps_booking_and_allows_retry(self):
        with patch('agenda.notifications.send_mail',side_effect=TimeoutError('private')):
            with self.captureOnCommitCallbacks(execute=True):
                booking=save_occupancy(self.user,self.data)
        self.assertTrue(Occupancy.objects.filter(pk=booking.pk).exists())
        item=BookingEmail.objects.get(occupancy=booking)
        self.assertIsNone(item.sent_at)
        self.assertEqual(item.last_error,'TimeoutError')
        self.assertTrue(deliver_safely(item.pk))
        self.assertEqual(len(mail.outbox),1)

    def test_rollback_does_not_queue_or_send(self):
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    save_occupancy(self.user,self.data)
                    raise RuntimeError('rollback')
        self.assertFalse(BookingEmail.objects.exists())
        self.assertEqual(len(mail.outbox),0)

    def test_conflict_does_not_queue_second_email(self):
        save_occupancy(self.user,self.data)
        with self.assertRaises(Problem):
            save_occupancy(self.user,{**self.data,'request_key':'conflict'})
        self.assertEqual(BookingEmail.objects.count(),1)
