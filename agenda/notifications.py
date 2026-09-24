import logging
from zoneinfo import ZoneInfo
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from .models import BookingEmail


def queue_confirmation(booking):
    tz = ZoneInfo('America/Sao_Paulo')
    start, end = booking.start.astimezone(tz), booking.end.astimezone(tz)
    interval = f'Saída/início: {start:%d/%m/%Y %H:%M}\nRetorno/término: {end:%d/%m/%Y %H:%M}'
    if booking.mode == 'day':
        interval = f'Reservado o dia todo em {start:%d/%m/%Y}\n' + interval
    body = (f'Olá, {booking.owner.first_name}.\n\nSua reserva foi confirmada.\n\n'
            f'Recurso: {booking.resource.name}\n{interval}\nHorário de Brasília\n'
            f'Responsável: {booking.owner.first_name}\nFinalidade: {booking.title}\n')
    if booking.resource.kind == 'vehicle':
        body += f'Destino: {booking.destination}\nCondutor: {booking.driver}\n\nAo atingir meio tanque, abasteça o veículo. Deixe o carro pronto para o próximo uso.\n'
    body += f'\nConsulte sua reserva em: {settings.PUBLIC_URL}\n\nTVTEC Agenda'
    item, _ = BookingEmail.objects.get_or_create(occupancy=booking, defaults={
        'recipient': booking.owner.email, 'subject': 'Reserva confirmada — TVTEC Agenda', 'body': body})
    transaction.on_commit(lambda: deliver_safely(item.pk))


def deliver_safely(pk):
    # SMTP failure must never turn a committed booking into an apparent failure.
    try:
        with transaction.atomic():
            item = BookingEmail.objects.select_for_update().get(pk=pk)
            if item.sent_at:
                return True
            item.attempts += 1
            try:
                if not settings.DEFAULT_FROM_EMAIL:
                    raise ValueError('Remetente não configurado')
                if settings.MAIL_MODE == 'resend' and not settings.RESEND_API_KEY:
                    raise ValueError('Resend não configurado')
                if send_mail(item.subject, item.body, settings.DEFAULT_FROM_EMAIL, [item.recipient], fail_silently=False) != 1:
                    raise RuntimeError('Envio não aceito')
                item.sent_at = timezone.now()
                item.last_error = ''
            except Exception as exc:
                # Store only the error class; provider errors may contain credentials/data.
                item.last_error = type(exc).__name__
            item.save(update_fields=['attempts', 'sent_at', 'last_error'])
            return bool(item.sent_at)
    except Exception:
        logging.getLogger(__name__).error('Confirmação de reserva pendente: %s', pk)
        return False
