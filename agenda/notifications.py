import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from .models import BookingEmail


class ResendDeliveryError(RuntimeError):
    """A safe, provider-neutral error for a failed Resend API request."""


def _send_resend(subject, body, recipient, idempotency_key):
    if not settings.RESEND_API_KEY:
        raise ResendDeliveryError('Resend não configurado')
    payload = json.dumps({
        'from': settings.DEFAULT_FROM_EMAIL,
        'to': [recipient],
        'subject': subject,
        'text': body,
    }).encode('utf-8')
    request = Request(
        'https://api.resend.com/emails', data=payload, method='POST', headers={
            'Authorization': f'Bearer {settings.RESEND_API_KEY}',
            'Content-Type': 'application/json',
            'Idempotency-Key': idempotency_key[:256],
            'User-Agent': 'TVTEC-Agenda/1.0',
        })
    try:
        with urlopen(request, timeout=15) as response:
            if response.status not in (200, 201):
                raise ResendDeliveryError('Resposta não aceita pelo Resend')
            data = json.loads(response.read().decode('utf-8'))
            if not data.get('id'):
                raise ResendDeliveryError('Resposta inválida do Resend')
            return data['id']
    except HTTPError as exc:
        raise ResendDeliveryError('Pedido recusado pelo Resend') from exc
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise ResendDeliveryError('Não foi possível conectar ao Resend') from exc


def send_transactional_email(subject, body, recipient, idempotency_key):
    """Send through Resend HTTPS in production, retaining SMTP/file support locally."""
    if not settings.DEFAULT_FROM_EMAIL:
        raise ValueError('Remetente não configurado')
    if settings.MAIL_MODE == 'resend':
        return _send_resend(subject, body, recipient, idempotency_key)
    if send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient], fail_silently=False) != 1:
        raise RuntimeError('Envio não aceito')
    return True


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
    # Delivery failure must never turn a committed booking into an apparent failure.
    try:
        with transaction.atomic():
            item = BookingEmail.objects.select_for_update().get(pk=pk)
            if item.sent_at:
                return True
            item.attempts += 1
            try:
                send_transactional_email(item.subject, item.body, item.recipient, f'booking-confirmation/{item.pk}')
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
