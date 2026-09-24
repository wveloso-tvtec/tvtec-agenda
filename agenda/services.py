import hashlib, json, secrets
import re
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from django.conf import settings
from django.db import transaction
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import User, Resource, Occupancy, Invitation, Audit, Settings, Attempt

TZ = ZoneInfo('America/Sao_Paulo')

class Problem(Exception):
    def __init__(self, message, status=400, **extra):
        self.message, self.status, self.extra = message, status, extra

def require_admin(user):
    user.refresh_from_db()
    if user.role != 'admin' or not user.is_active or not user.verified: raise Problem('Você não tem permissão administrativa.',403)

def text(data, key, maximum, required=False):
    value = data.get(key,'')
    if not isinstance(value,str): raise Problem('Campo inválido: '+key)
    value = value.strip()
    if len(value)>maximum or (required and not value): raise Problem('Preencha corretamente: '+key)
    return value

def full_name(data, key='name'):
    value=' '.join(text(data,key,150,True).split())
    parts=value.split(' ')
    if len(parts)<2 or any(len(part)<2 for part in parts):
        raise Problem('Informe o nome completo, com nome e sobrenome.')
    if not re.fullmatch(r"[\wÀ-ÖØ-öø-ÿ'’. -]+",value,flags=re.UNICODE):
        raise Problem('O nome completo contém caracteres inválidos.')
    return value

def boolean(data, key, default=False):
    v = data.get(key,default)
    if not isinstance(v,bool): raise Problem('Valor inválido: '+key)
    return v

def integer(data,key,default=None):
    v=data.get(key,default)
    if isinstance(v,bool) or not isinstance(v,int): raise Problem('Número inválido: '+key)
    return v

def audit(user,action,entity,before=None,after=None,reason=''):
    Audit.objects.create(actor=user,action=action,entity=str(entity),changes={'antes':before,'depois':after},reason=reason)

def public_user(u):
    return {'id':u.id,'name':u.first_name or u.email,'email':u.email,'sector':u.sector,'role':u.role,'rooms':u.rooms,'vehicles':u.vehicles,'active':u.is_active,'verified':u.verified}

def resource_data(r):
    return {'id':r.id,'key':r.key,'name':r.name,'description':r.description,'kind':r.kind,'active':r.active,'opens':r.opens,'closes':r.closes,'periods':r.periods}

def occupancy_data(o,viewer):
    result = {'id':o.id,'resource':o.resource_id,'start':o.start.isoformat(),'end':o.end.isoformat(),'owner':o.owner_id,'responsible':o.owner.first_name or o.owner.email,'kind':o.kind,'cancelled':o.cancelled,'updated':o.updated.isoformat()}
    result['all_day'] = o.kind == 'booking' and o.mode == 'day'
    if viewer.role=='admin' or viewer.id==o.owner_id:
        result.update({k:getattr(o,k) for k in ['title','notes','destination','driver','mode']})
    return result

def local_datetime(value):
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=TZ)
        dt=dt.astimezone(TZ)
        if dt.second or dt.microsecond: raise ValueError()
        return dt
    except (ValueError, TypeError): raise Problem('Informe data e horário válidos, com precisão de minutos.')

def valid_hours(resource,start,end):
    if resource.kind=='room' and start.date()!=end.date(): return False
    day=start.date()
    while day<=end.date():
        midnight=datetime.combine(day,time.min,TZ)
        next_day=midnight+timedelta(days=1)
        left,right=max(start,midnight),min(end,next_day)
        if left<right and (left < midnight+timedelta(minutes=resource.opens) or right>midnight+timedelta(minutes=resource.closes)): return False
        day += timedelta(days=1)
    return True

def validate_interval(resource,start,end,kind='booking',allow_past=False):
    if not resource.active: raise Problem('Este recurso está desativado.')
    if end<=start: raise Problem('O término deve ser posterior ao início.')
    if not allow_past and start<timezone.now(): raise Problem('O início não pode estar no passado.')
    if end-start>timedelta(days=366): raise Problem('O intervalo máximo é de 366 dias.')
    if kind=='booking':
        if end-start<timedelta(minutes=30): raise Problem('A duração mínima é de 30 minutos.')
        exceptional=resource.kind=='room' and end.hour==23 and end.minute==59
        if start.minute%30 or (end.minute%30 and not exceptional): raise Problem('Use intervalos de 30 minutos; salas aceitam término excepcional às 23h59.')
        if not valid_hours(resource,start,end): raise Problem('O intervalo está fora do funcionamento do recurso. Salas não atravessam a meia-noite.')

def conflicts(resource,start,end,exclude=None):
    qs=Occupancy.objects.filter(resource=resource,cancelled=False,start__lt=end,end__gt=start)
    if exclude: qs=qs.exclude(pk=exclude)
    return qs.order_by('start')

def conflict_error(resource,start,end,exclude=None):
    other=conflicts(resource,start,end,exclude).first()
    if not other: return
    a,b=other.start.astimezone(TZ),other.end.astimezone(TZ)
    candidate=b
    for _ in range(20):
        busy=conflicts(resource,candidate,candidate+(end-start),exclude).first()
        if not busy: break
        candidate=busy.end.astimezone(TZ)
    # Suggestions also respect the same slot and opening rules as saving.
    candidate=candidate.replace(second=0,microsecond=0)
    if candidate.minute%30: candidate += timedelta(minutes=30-candidate.minute%30)
    suggestion=None
    try:
        validate_interval(resource,candidate,candidate+(end-start))
        if not conflicts(resource,candidate,candidate+(end-start),exclude).exists(): suggestion={'start':candidate.isoformat(),'end':(candidate+(end-start)).isoformat()}
    except Problem: pass
    raise Problem(f'Este recurso está ocupado de {a:%d/%m %Hh%M} até {b:%d/%m %Hh%M}. Escolha outro horário.',409,suggestion=suggestion)

@transaction.atomic
def save_occupancy(user,data):
    # Re-read authorization after acquiring SQLite's immediate write transaction.
    user=User.objects.get(pk=user.pk)
    if not user.is_active or not user.verified: raise Problem('Acesso desativado.',403)
    existing=None
    if data.get('id'):
        existing=Occupancy.objects.get(pk=data['id'])
        if existing.cancelled: raise Problem('Uma reserva cancelada não pode ser alterada.')
        if user.role!='admin' and (existing.owner_id!=user.id or existing.start<=timezone.now()): raise Problem('Você pode editar apenas suas reservas futuras.',403)
        if data.get('updated')!=existing.updated.isoformat(): raise Problem('Esta reserva mudou. Atualize a agenda e abra novamente.',409)
    kind = existing.kind if existing else data.get('kind','booking')
    if kind not in ('booking','block'): raise Problem('Tipo de ocupação inválido.')
    if kind=='block': require_admin(user)
    resource=Resource.objects.get(pk=integer(data,'resource'))
    if user.role!='admin' and not (user.rooms if resource.kind=='room' else user.vehicles): raise Problem('Você não tem permissão para reservar este tipo de recurso.',403)
    reason=text(data,'reason',1000)
    exceptional=existing and (existing.owner_id!=user.id or existing.start<=timezone.now())
    if exceptional and not reason: raise Problem('Informe a justificativa da alteração administrativa.')
    key=text(data,'request_key',64,not existing)
    fingerprint=hashlib.sha256(json.dumps({k:v for k,v in data.items() if k!='request_key'},sort_keys=True).encode()).hexdigest()
    if not existing:
        previous=Occupancy.objects.filter(owner=user,request_key=key).first()
        if previous:
            if previous.fingerprint!=fingerprint: raise Problem('A chave desta solicitação já foi usada para outros dados.',409)
            return previous
    start,end=local_datetime(data.get('start')),local_datetime(data.get('end'))
    mode=data.get('mode','hours')
    if mode not in ('hours','period','day'): raise Problem('Modalidade inválida.')
    if kind=='booking' and resource.kind=='vehicle':
        if mode=='day' and (start.time()!=time.min or end!=start+timedelta(days=1)): raise Problem('Dia todo ocupa 00h00 até 00h00 do dia seguinte.')
        if mode=='period':
            period=resource.periods.get(data.get('period'))
            if not period: raise Problem('O administrador ainda não configurou este período.')
            midnight=datetime.combine(start.date(),time.min,TZ)
            if start!=midnight+timedelta(minutes=period[0]) or end!=midnight+timedelta(minutes=period[1]): raise Problem('O intervalo não corresponde ao período configurado.')
    validate_interval(resource,start,end,kind,allow_past=bool(existing and user.role=='admin'))
    if kind=='block':
        affected=list(conflicts(resource,start,end,existing.pk if existing else None).select_related('owner'))
        if affected: raise Problem('O bloqueio afeta ocupações existentes. Resolva cada uma em Gestão de reservas antes de continuar.',409,affected=[occupancy_data(o,user) for o in affected])
    conflict_error(resource,start,end,existing.pk if existing else None)
    before=occupancy_data(existing,user) if existing else None
    obj=existing or Occupancy(owner=user,request_key=key,fingerprint=fingerprint)
    obj.resource,obj.start,obj.end,obj.kind,obj.mode=resource,start,end,kind,mode
    obj.title=text(data,'title',180,True)
    obj.notes=text(data,'notes',2000)
    obj.destination=text(data,'destination',250,kind=='booking' and resource.kind=='vehicle')
    obj.driver=text(data,'driver',150,kind=='booking' and resource.kind=='vehicle')
    obj.save()
    audit(user,'Reserva alterada' if existing else ('Bloqueio criado' if kind=='block' else 'Reserva criada'),f'ocupacao:{obj.id}',before,occupancy_data(obj,user),reason)
    if not existing and kind == 'booking':
        from .notifications import queue_confirmation
        queue_confirmation(obj)
    return obj

@transaction.atomic
def cancel_occupancy(user,data):
    user=User.objects.get(pk=user.pk)
    if not user.is_active: raise Problem('Acesso desativado.',403)
    obj=Occupancy.objects.get(pk=integer(data,'id'))
    if user.role!='admin' and (obj.owner_id!=user.id or obj.start<=timezone.now() or obj.kind=='block'): raise Problem('Você pode cancelar apenas suas reservas futuras.',403)
    reason=text(data,'reason',1000)
    if user.role=='admin' and (obj.owner_id!=user.id or obj.start<=timezone.now()) and not reason: raise Problem('Informe a justificativa do cancelamento.')
    if not obj.cancelled:
        before=occupancy_data(obj,user)
        obj.cancelled=True
        obj.save()
        audit(user,'Ocupação cancelada',f'ocupacao:{obj.id}',before,occupancy_data(obj,user),reason)

def check_email(email):
    email=email.strip().lower()
    try: validate_email(email)
    except ValidationError: raise Problem('Informe um e-mail profissional válido.')
    domains=Settings.objects.get_or_create(pk=1)[0].domains
    if domains and email.rsplit('@',1)[1] not in domains: raise Problem('O domínio deste e-mail não está autorizado.')
    return email

def ensure_mail():
    if settings.MAIL_MODE == 'resend':
        if not settings.RESEND_API_KEY or not settings.DEFAULT_FROM_EMAIL:
            raise Problem('O envio pelo Resend ainda não foi configurado. Contate a administração.',503)
        return
    if settings.MAIL_MODE!='file' and (not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL): raise Problem('O envio de e-mails ainda não foi configurado. Contate a administração.',503)

def send_token(user,purpose='invite'):
    ensure_mail()
    raw=secrets.token_urlsafe(40)
    expires=timezone.now()+timedelta(hours=48 if purpose=='invite' else 1)
    # Call inside a transaction; a failed delivery does not invalidate the old link.
    Invitation.objects.filter(user=user,purpose=purpose,used=False).update(used=True)
    invitation=Invitation.objects.create(user=user,purpose=purpose,digest=hashlib.sha256(raw.encode()).hexdigest(),expires=expires)
    link=f'{settings.PUBLIC_URL}/ativar?token={raw}'
    subject='Convite para TVTEC Agenda' if purpose=='invite' else 'Redefinição de senha — TVTEC Agenda'
    from .notifications import send_transactional_email
    send_transactional_email(subject,f'Olá, {user.first_name or user.email}.\n\nPara verificar seu e-mail e definir sua senha, acesse:\n{link}\n\nEste link é individual e expira em {expires.astimezone(TZ):%d/%m/%Y às %Hh%M}. Se não reconhece esta solicitação, ignore a mensagem.\n\nTVTEC Agenda',user.email,f'{purpose}/{invitation.pk}')

@transaction.atomic
def invite_user(actor,data):
    require_admin(actor)
    email=check_email(text(data,'email',254,True))
    if User.objects.filter(email=email).exists(): raise Problem('Este e-mail já existe. Use reenviar convite ou editar acesso.')
    role=data.get('role','collaborator')
    if role not in ('admin','collaborator'): raise Problem('Perfil inválido.')
    u=User(username=email,email=email,first_name=full_name(data),sector=text(data,'sector',120),role=role,rooms=boolean(data,'rooms',True),vehicles=boolean(data,'vehicles'),is_active=False)
    u.set_unusable_password(); u.save()
    send_token(u)
    audit(actor,'Convite enviado',f'usuario:{u.id}',None,public_user(u))
    return u

@transaction.atomic
def update_user(actor,data):
    require_admin(actor)
    u=User.objects.get(pk=integer(data,'id'))
    before=public_user(u)
    role=data.get('role',u.role)
    active=boolean(data,'active',u.is_active)
    if role not in ('admin','collaborator'): raise Problem('Perfil inválido.')
    if active and not u.verified: raise Problem('O usuário deve aceitar o convite e verificar seu e-mail.')
    if u.role=='admin' and u.is_active and (role!='admin' or not active) and not User.objects.filter(role='admin',is_active=True,verified=True).exclude(pk=u.pk).exists(): raise Problem('Mantenha pelo menos um administrador ativo.',409)
    future=list(Occupancy.objects.filter(owner=u,cancelled=False,end__gt=timezone.now()).select_related('owner'))
    if not active and u.is_active and future:
        choice=data.get('reservations')
        current=sorted(o.id for o in future)
        if choice not in ('keep','cancel') or sorted(data.get('affected',[]))!=current:
            raise Problem('Revise as reservas em andamento e futuras e decida se deseja mantê-las ou cancelá-las.',409,affected=[occupancy_data(o,actor) for o in future])
        if choice=='cancel':
            for o in future:
                o.cancelled=True; o.save()
                audit(actor,'Cancelada por desativação',f'ocupacao:{o.id}',None,{'cancelled':True},'Cancelamento escolhido ao desativar usuário')
    u.role,u.is_active=role,active
    u.rooms=boolean(data,'rooms',u.rooms); u.vehicles=boolean(data,'vehicles',u.vehicles)
    u.first_name=full_name(data); u.sector=text(data,'sector',120)
    u.save()
    audit(actor,'Acesso alterado',f'usuario:{u.id}',before,public_user(u))
    return u

@transaction.atomic
def save_resource(actor,data):
    require_admin(actor)
    r=Resource.objects.get(pk=integer(data,'id'))
    before=resource_data(r)
    r.name=text(data,'name',100,True); r.description=text(data,'description',500)
    r.active=boolean(data,'active',r.active)
    r.opens=integer(data,'opens'); r.closes=integer(data,'closes')
    limit=1439 if r.kind=='room' else 1440
    if not 0<=r.opens<r.closes<=limit: raise Problem('Horário de funcionamento inválido.')
    if r.opens%30 or (r.closes%30 and r.closes!=1439): raise Problem('Funcionamento deve respeitar blocos de 30 minutos ou término às 23h59.')
    periods=data.get('periods',{})
    if not isinstance(periods,dict) or any(k not in ('morning','afternoon') for k in periods): raise Problem('Períodos inválidos.')
    for pair in periods.values():
        if not isinstance(pair,list) or len(pair)!=2 or any(type(v)!=int for v in pair) or not r.opens<=pair[0]<pair[1]<=r.closes or pair[0]%30 or pair[1]%30: raise Problem('Configure períodos dentro do funcionamento, em blocos de 30 minutos.')
    r.periods=periods
    affected=[o for o in Occupancy.objects.filter(resource=r,cancelled=False,end__gt=timezone.now()).select_related('owner') if not r.active or (o.kind=='booking' and not valid_hours(r,o.start.astimezone(TZ),o.end.astimezone(TZ)))]
    if affected: raise Problem('Há ocupações afetadas. Reagende ou cancele explicitamente cada uma antes de alterar o recurso.',409,affected=[occupancy_data(o,actor) for o in affected])
    r.save(); audit(actor,'Recurso alterado',f'recurso:{r.id}',before,resource_data(r))
    return r

@transaction.atomic
def throttle(key,limit=10):
    key=hashlib.sha256(key.encode()).hexdigest()
    a,_=Attempt.objects.get_or_create(key=key,defaults={'since':timezone.now()})
    if a.since<timezone.now()-timedelta(minutes=15): a.count=0; a.since=timezone.now()
    if a.count>=limit: return False
    a.count+=1; a.save()
    return True
