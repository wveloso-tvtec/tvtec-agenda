# Configurar o Resend

O TVTEC Agenda envia confirmações de reservas, convites e redefinições de senha pela **API HTTPS do Resend**. Essa integração usa a porta HTTPS padrão (443), adequada ao Render Free, e não exige SMTP.

## 1. Verificar o domínio de envio

Abra [Domains no Resend](https://resend.com/domains) e adicione um domínio ou subdomínio controlado pela Fundação, como `notificacoes.tvtecjundiai.com.br`.

O Resend exibirá registros DNS. Envie ao responsável pelo DNS os campos tipo, nome, valor e prioridade exatamente como mostrados. Não substitua os registros de recebimento da instituição. Volte ao painel e aguarde o status **Verified**.

## 2. Criar a chave

Em [API Keys](https://resend.com/api-keys), crie a chave `TVTEC Agenda` com permissão de envio e, se disponível, limite-a ao domínio verificado. Guarde-a somente para as variáveis de ambiente do Render. Nunca a coloque no GitHub, em HTML ou no arquivo `.env` enviado ao repositório.

## 3. Variáveis no Render

Em **Environment** do serviço Render, cadastre:

```dotenv
MAIL_MODE=resend
RESEND_API_KEY=re_sua_chave_real
DEFAULT_FROM_EMAIL=TVTEC Agenda <agenda@notificacoes.tvtecjundiai.com.br>
PUBLIC_URL=https://seu-servico.onrender.com
```

O endereço do remetente deve usar o domínio verificado. `PUBLIC_URL` é o endereço público do TVTEC Agenda; após o primeiro deploy, copie a URL exibida pelo Render e use-a também em `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS`.

## 4. Testar

```sh
python manage.py test_resend
python manage.py test_resend --to wveloso@tvtecjundiai.com.br
```

O primeiro comando apenas valida a configuração e não mostra a chave. O segundo envia uma mensagem real sem criar reserva. Confira a caixa de entrada, spam e o painel [Emails do Resend](https://resend.com/emails).

## Entrega e reenvio

Cada nova reserva cria uma confirmação para o responsável, com recurso, datas, horários de Brasília e finalidade. Veículos incluem condutor e destino. A reserva é mantida se o envio falhar; a tentativa fica registrada para reenvio com:

```sh
python manage.py send_booking_emails
```

Em hospedagens com tarefas agendadas, execute esse comando periodicamente no mesmo banco e ambiente da aplicação. O Render Free não oferece cron jobs: as novas reservas continuam sendo enviadas imediatamente, e um reenvio pendente pode ser executado quando houver uma instância com os mesmos dados ou ao migrar para um plano com cron job.

O pedido de criação de e-mail usa uma chave de idempotência do Resend, e o aplicativo também registra `sent_at` no banco. Isso reduz mensagens duplicadas; a aceitação pelo provedor ainda não é confirmação de entrega na caixa.

## Se não enviar

| Situação | O que conferir |
| --- | --- |
| Chave ausente ou recusada | `RESEND_API_KEY`, validade e permissão de envio. |
| Remetente recusado | Domínio do remetente verificado e autorizado para a chave. |
| Falha de conexão | Saída HTTPS para `api.resend.com` na porta 443. |
| Aceito, mas não chegou | Eventos, rejeições, spam e limites no painel do Resend. |
| Reserva salva sem mensagem | Execute `send_booking_emails`; não recrie a reserva. |

Referências oficiais: [envio por API](https://resend.com/docs/api-reference/emails/send-email), [chaves de idempotência](https://resend.com/docs/dashboard/emails/idempotency-keys), [domínios](https://resend.com/docs/dashboard/domains/introduction).
