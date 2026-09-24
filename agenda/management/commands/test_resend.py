from email.utils import parseaddr
from smtplib import SMTPAuthenticationError, SMTPRecipientsRefused, SMTPSenderRefused
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email


class Command(BaseCommand):
    help = 'Verifica a configuração Resend; --to envia uma mensagem de teste sem criar reserva.'

    def add_arguments(self, parser):
        parser.add_argument('--to', dest='recipient', help='Destinatário do teste real')

    def handle(self, *args, **options):
        if settings.MAIL_MODE != 'resend':
            raise CommandError('Configure MAIL_MODE=resend e reinicie o ambiente.')
        if not settings.RESEND_API_KEY:
            raise CommandError('Configure RESEND_API_KEY no ambiente do servidor ou no .env local.')
        try:
            validate_email(parseaddr(settings.DEFAULT_FROM_EMAIL)[1])
            if options['recipient']:
                validate_email(options['recipient'])
        except ValidationError:
            raise CommandError('Informe DEFAULT_FROM_EMAIL e destinatário com endereços válidos.') from None
        self.stdout.write('Configuração local presente. A chave não será exibida.')
        if not options['recipient']:
            self.stdout.write('Nenhuma conexão feita. Use --to EMAIL para testar autenticação e envio.')
            return
        try:
            sent = send_mail('Teste de conexão — TVTEC Agenda',
                             'Este é um teste de envio do TVTEC Agenda pelo Resend. Nenhuma reserva foi criada.',
                             settings.DEFAULT_FROM_EMAIL, [options['recipient']], fail_silently=False)
            if sent != 1:
                raise CommandError('O provedor não aceitou a mensagem.')
        except SMTPAuthenticationError:
            raise CommandError('Autenticação recusada. Confira a chave e sua permissão de envio.') from None
        except (SMTPRecipientsRefused, SMTPSenderRefused):
            raise CommandError('Remetente ou destinatário recusado. Confira o domínio verificado e as restrições da conta Resend.') from None
        except CommandError:
            raise
        except Exception:
            raise CommandError('Falha no envio. Confira domínio, chave, acesso à porta 465 e o painel Resend.') from None
        self.stdout.write(self.style.SUCCESS('Mensagem aceita pelo Resend. Confirme o recebimento e o estado da entrega no painel.'))
