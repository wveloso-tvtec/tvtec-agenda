from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from agenda.models import User
from agenda.services import send_token, audit

class Command(BaseCommand):
    help='Envia convite de verificação ao administrador inicial. Nunca define senha padrão.'
    def handle(self,*args,**options):
        try:
            with transaction.atomic():
                email='wveloso@tvtecjundiai.com.br'
                u,created=User.objects.get_or_create(email=email,defaults={'username':email,'first_name':'Witter Veloso','role':'admin','is_active':False,'rooms':True,'vehicles':True})
                if not created and u.verified: raise CommandError('Conta já verificada. Alterações de perfil exigem um administrador autenticado.')
                if not created and u.role!='admin': raise CommandError('A conta existente não é administradora. Nenhuma promoção foi realizada.')
                if created: u.set_unusable_password(); u.save()
                send_token(u)
                audit(None,'Administrador inicial convidado',f'usuario:{u.id}')
            self.stdout.write(self.style.SUCCESS('Convite enviado pelo backend configurado. O acesso só será ativado após verificar o e-mail e definir a senha.'))
        except CommandError: raise
        except Exception as exc: raise CommandError(str(exc)) from exc
