from io import StringIO
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from django.core.management import call_command, CommandError
from smtplib import SMTPAuthenticationError


@override_settings(MAIL_MODE='resend', RESEND_API_KEY='dummy-only-for-test', DEFAULT_FROM_EMAIL='Agenda <agenda@example.test>')
class ResendCommandTests(SimpleTestCase):
    @patch('agenda.management.commands.test_resend.send_mail')
    def test_check_does_not_send_or_print_key(self, send):
        output=StringIO()
        call_command('test_resend', stdout=output)
        send.assert_not_called()
        self.assertNotIn('dummy-only-for-test', output.getvalue())

    @patch('agenda.management.commands.test_resend.send_mail', return_value=1)
    def test_explicit_recipient_sends(self, send):
        call_command('test_resend', to='owner@example.test', stdout=StringIO())
        self.assertEqual(send.call_args.args[3], ['owner@example.test'])

    @override_settings(RESEND_API_KEY='')
    def test_missing_key(self):
        with self.assertRaises(CommandError):
            call_command('test_resend', stdout=StringIO())

    @patch('agenda.management.commands.test_resend.send_mail', side_effect=SMTPAuthenticationError(535,b'secret-detail'))
    def test_authentication_error_is_safe(self, send):
        with self.assertRaises(CommandError) as error:
            call_command('test_resend', to='owner@example.test', stdout=StringIO())
        self.assertNotIn('secret-detail', str(error.exception))
