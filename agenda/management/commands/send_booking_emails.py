from django.core.management.base import BaseCommand
from agenda.models import BookingEmail
from agenda.notifications import deliver_safely


class Command(BaseCommand):
    help = 'Tenta enviar até 100 confirmações pendentes. Agende a execução a cada minuto.'

    def handle(self, *args, **options):
        ids = list(BookingEmail.objects.filter(sent_at__isnull=True).order_by('attempts', 'id').values_list('id', flat=True)[:100])
        sent = sum(deliver_safely(pk) for pk in ids)
        self.stdout.write(f'{sent} aceitas pelo provedor; {len(ids)-sent} permanecem pendentes.')
