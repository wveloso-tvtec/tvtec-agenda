from email.utils import parseaddr
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from agenda.notifications import ResendDeliveryError, send_transactional_email


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
            send_transactional_email('Teste de conexão — TVTEC Agenda',
                                     'Este é um teste de envio do TVTEC Agenda pelo Resend. Nenhuma reserva foi criada.',
                                     options['recipient'], 'resend-configuration-test')
        except ResendDeliveryError:
            raise CommandError('Falha no envio. Confira a chave, o domínio verificado, a saída HTTPS e o painel Resend.') from None
        except Exception:
            raise CommandError('Falha no envio. Confira a configuração do Resend.') from None
        self.stdout.write(self.style.SUCCESS('Mensagem aceita pelo Resend. Confirme o recebimento e o estado da entrega no painel.'))
