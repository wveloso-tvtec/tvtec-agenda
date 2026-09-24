import json, hashlib, logging
from datetime import timedelta
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction, IntegrityError, OperationalError
from django.utils import timezone
from .models import *
from .services import *

@ensure_csrf_cookie
def index(request): return render(request,'index.html',{'demo_mode':settings.DEMO_MODE})

def csrf_failure(request,reason=''): return JsonResponse({'error':'Sua sessão de segurança expirou. Atualize a página e tente novamente.'},status=403)

def api(request,action):
    try:
        if request.method not in ('GET','POST'): raise Problem('Método não permitido.',405)
        if request.method=='POST':
            if len(request.body)>30000: raise Problem('Solicitação muito grande.',413)
            try: data=json.loads(request.body or '{}')
            except (ValueError,UnicodeError): raise Problem('Dados inválidos.')
            if not isinstance(data,dict): raise Problem('Dados inválidos.')
        else: data=request.GET
        read_actions={'session','resources','overview','occupancies','mine','users','audit','settings','token'}
        if (action in read_actions)!=(request.method=='GET'): raise Problem('Método não permitido.',405)
        if action in ('login','recover','activate'):
            ip=request.META.get('REMOTE_ADDR','unknown')
            if not throttle(action+':ip:'+ip,30): raise Problem('Muitas tentativas. Tente novamente em 15 minutos.',429)
            email=text(data,'email',254).lower()
            if email and not throttle(action+':email:'+email,10): raise Problem('Muitas tentativas. Tente novamente em 15 minutos.',429)
        if action=='login':
            u=authenticate(request,username=email,password=text(data,'password',256,True))
            if not u or not u.verified: raise Problem('E-mail ou senha inválidos, ou acesso inativo. Consulte a administração.',401)
            login(request,u)
            return JsonResponse({'user':public_user(u)})
        if action=='logout':
            logout(request); return JsonResponse({'ok':True})
        if action=='recover':
            ensure_mail()
            u=User.objects.filter(email=email,is_active=True,verified=True).first()
            if u:
                with transaction.atomic(): send_token(u,'reset')
            return JsonResponse({'ok':True,'message':'Se o e-mail estiver autorizado e ativo, enviaremos as instruções.'})
        if action in ('token','activate'):
            raw=data.get('token','')
            if not isinstance(raw,str) or len(raw)>200: raise Problem('Convite inválido ou expirado.',410)
            with transaction.atomic():
                inv=Invitation.objects.select_related('user').filter(digest=hashlib.sha256(raw.encode()).hexdigest(),used=False,expires__gt=timezone.now()).first()
                if not inv or (inv.purpose=='reset' and not inv.user.is_active): raise Problem('Este link é inválido ou expirou. Solicite um novo à administração.',410)
                if action=='token': return JsonResponse({'email':inv.user.email,'purpose':inv.purpose})
                password=text(data,'password',256,True)
                validate_password(password,inv.user)
                u=inv.user; u.set_password(password)
                if inv.purpose=='invite': u.verified=True; u.is_active=True
                u.save(); Invitation.objects.filter(user=u,used=False).update(used=True)
                audit(u,'Senha definida e e-mail verificado' if inv.purpose=='invite' else 'Senha redefinida',f'usuario:{u.id}')
            return JsonResponse({'ok':True})
        if not request.user.is_authenticated:
            raise Problem('Entre com sua conta autorizada. Se seu acesso foi desativado, procure a administração.',401)
        user=User.objects.get(pk=request.user.pk)
        if not user.is_active or not user.verified: raise Problem('Seu acesso foi desativado. Consulte a administração.',403)
        if action=='session': return JsonResponse({'user':public_user(user)})
        if action=='resources': return JsonResponse({'resources':[resource_data(r) for r in Resource.objects.order_by('id')]})
        if action=='overview':
            now=timezone.now(); day=now.astimezone(TZ).replace(hour=0,minute=0,second=0,microsecond=0)
            qs=Occupancy.objects.filter(cancelled=False).select_related('owner')
            records={o.id:o for o in qs.filter(start__lt=day+timedelta(days=1),end__gt=day)}
            for r in Resource.objects.all():
                for o in qs.filter(resource=r,end__gt=now).order_by('start')[:2]: records[o.id]=o
            return JsonResponse({'occupancies':[occupancy_data(o,user) for o in sorted(records.values(),key=lambda o:o.start)]})
        if action in ('occupancies','mine'):
            qs=Occupancy.objects.select_related('owner','resource').order_by('start')
            if action=='mine': qs=qs.filter(owner=user)
            else:
                start=local_datetime(data.get('start')); end=local_datetime(data.get('end'))
                if end<=start or end-start>timedelta(days=367): raise Problem('Consulte um intervalo de até 366 dias.')
                qs=qs.filter(start__lt=end,end__gt=start)
                if user.role!='admin' or data.get('cancelled')!='1': qs=qs.filter(cancelled=False)
            return JsonResponse({'occupancies':[occupancy_data(o,user) for o in qs]})
        if action=='save': return JsonResponse({'occupancy':occupancy_data(save_occupancy(user,data),user)})
        if action=='cancel': cancel_occupancy(user,data); return JsonResponse({'ok':True})
        require_admin(user)
        if action=='users': return JsonResponse({'users':[public_user(u) for u in User.objects.order_by('first_name','email')]})
        if action=='invite': return JsonResponse({'user':public_user(invite_user(user,data))})
        if action=='update-user': return JsonResponse({'user':public_user(update_user(user,data))})
        if action=='resend':
            u=User.objects.get(pk=integer(data,'id'))
            if u.verified: raise Problem('Este usuário já verificou o e-mail. Use recuperação de senha.')
            with transaction.atomic(): send_token(u); audit(user,'Convite reenviado',f'usuario:{u.id}')
            return JsonResponse({'ok':True})
        if action=='save-resource': return JsonResponse({'resource':resource_data(save_resource(user,data))})
        if action=='settings': return JsonResponse({'domains':Settings.objects.get_or_create(pk=1)[0].domains})
        if action=='save-settings':
            domains=data.get('domains',[])
            if not isinstance(domains,list) or len(domains)>30: raise Problem('Lista de domínios inválida.')
            for d in domains:
                if not isinstance(d,str) or len(d)>250 or '@' in d: raise Problem('Domínio inválido.')
                try: validate_email('usuario@'+d)
                except ValidationError: raise Problem('Domínio inválido.')
            with transaction.atomic():
                s,_=Settings.objects.get_or_create(pk=1); before=s.domains
                s.domains=sorted(set(d.lower() for d in domains)); s.save()
                audit(user,'Domínios alterados','configuracao:1',before,s.domains)
            return JsonResponse({'ok':True})
        if action=='audit':
            page=max(1,min(int(data.get('page',1)),100000))
            qs=Audit.objects.select_related('actor').order_by('-id')
            return JsonResponse({'total':qs.count(),'entries':[{'id':a.id,'at':a.at.isoformat(),'actor':a.actor.first_name or a.actor.email if a.actor else 'Provisionamento','action':a.action,'entity':a.entity,'changes':a.changes,'reason':a.reason} for a in qs[(page-1)*50:page*50]]})
        raise Problem('Operação não encontrada.',404)
    except Problem as e: return JsonResponse({'error':e.message,**e.extra},status=e.status)
    except ValidationError as e: return JsonResponse({'error':' '.join(e.messages)},status=400)
    except ObjectDoesNotExist: return JsonResponse({'error':'Registro não encontrado.'},status=404)
    except IntegrityError: return JsonResponse({'error':'Conflito: este recurso foi ocupado ou a solicitação já existe. Atualize a agenda e tente novamente.'},status=409)
    except OperationalError:
        logging.exception('Falha no banco')
        return JsonResponse({'error':'Não foi possível acessar os dados. Tente novamente em instantes.'},status=503)
    except (ValueError,TypeError,KeyError): return JsonResponse({'error':'Revise os campos informados.'},status=400)
    except Exception:
        logging.exception('Falha na operação %s',action)
        return JsonResponse({'error':'Não foi possível concluir. Seus dados do formulário foram preservados. Tente novamente ou consulte a administração.'},status=503)
