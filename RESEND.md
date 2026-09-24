# Configurar o Resend

## Passo a passo para Witter

### 1. Verificar o domínio de envio

Acesse https://resend.com/domains com a conta que será usada pela TVTEC. Adicione um domínio ou subdomínio que a instituição controla. Exemplo: `notificacoes.tvtecjundiai.com.br` (é uma sugestão; não está configurado automaticamente).

O painel exibirá os registros DNS necessários. Envie ao responsável pelo DNS os campos tipo, nome, valor e prioridade exatamente como apresentados. Não substitua os registros de recebimento de e-mail institucional: cadastre apenas os registros solicitados para o domínio/subdomínio de envio. Não é necessário ativar recebimento no Resend. Volte ao painel e aguarde o domínio ficar verificado. Os valores DNS são exclusivos da conta; este guia não os inventa.

### 2. Criar a chave

Em https://resend.com/api-keys, crie uma chave chamada `TVTEC Agenda`, com permissão de envio (Sending access), restrita ao domínio escolhido quando essa opção estiver disponível. Guarde a chave para preencher o ambiente do servidor. Não coloque a chave no GitHub, no HTML ou na conversa.

### 3. Configurar o projeto

Na hospedagem, abra a área de variáveis de ambiente e preencha os quatro campos abaixo. Para testar localmente, edite o arquivo `.env` dentro da pasta `tvtec-agenda`, ao lado de `manage.py`, preservando SECRET_KEY e as demais configurações existentes. Substitua os exemplos pelos valores reais:

```dotenv
MAIL_MODE=resend
RESEND_API_KEY=SUA_CHAVE_REAL
DEFAULT_FROM_EMAIL=TVTEC Agenda <agenda@notificacoes.tvtecjundiai.com.br>
PUBLIC_URL=https://ENDERECO_PUBLICO_DA_AGENDA
```

O endereço do remetente deve pertencer ao domínio verificado no passo 1. Se verificar outro domínio, ajuste o remetente. PUBLIC_URL é o endereço do site, não o domínio do Resend; localmente mantenha `http://127.0.0.1:8765`. Em produção use a URL HTTPS definitiva. Valores definidos no ambiente do processo têm prioridade sobre o arquivo `.env`.

O código já configura automaticamente host `smtp.resend.com`, porta 465, SSL, usuário `resend` e a chave como senha. Não é necessário preencher EMAIL_HOST_PASSWORD. Confirmações de reserva, convites e recuperação passam a usar o Resend.

### 4. Aplicar e reiniciar

No terminal da hospedagem, dentro da pasta do projeto e usando o Python do ambiente virtual:

```sh
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py test_resend
```

O último comando verifica a presença e o formato da configuração, sem se conectar ao Resend ou exibir a chave. Reinicie o serviço da aplicação para carregar as variáveis novas.

No Windows atual, os comandos equivalentes, executados na pasta desta tarefa, são:

```powershell
& '.\work\venv\Scripts\python.exe' '.\outputs\tvtec-agenda\manage.py' migrate --noinput
& '.\work\venv\Scripts\python.exe' '.\outputs\tvtec-agenda\manage.py' test_resend
```

Se instalou o ZIP usando start-local.ps1, use `.\.venv\Scripts\python.exe` dentro da pasta extraída. Uma variável MAIL_MODE=file já definida no terminal deve ser removida ou alterada para resend, pois prevalece sobre o .env.

### 5. Enviar o teste

Após configurar, execute na hospedagem:

```sh
python manage.py test_resend --to wveloso@tvtecjundiai.com.br
```

No computador atual:

```powershell
& '.\work\venv\Scripts\python.exe' '.\outputs\tvtec-agenda\manage.py' test_resend --to wveloso@tvtecjundiai.com.br
```

Este comando envia uma mensagem real para o endereço indicado, sem criar uma reserva. Confira a caixa de entrada e spam, e a mensagem em https://resend.com/emails. A resposta de aceitação SMTP não comprova que a mensagem chegou à caixa.

### 6. Ativar a recuperação de falhas

As confirmações são tentadas automaticamente após cada nova reserva. Para recuperar envios pendentes, configure um trabalho agendado na hospedagem, a cada minuto, com o comando `python manage.py send_booking_emails`. Ele deve usar o mesmo código, variáveis e banco da aplicação. Evite execuções sobrepostas.

Em um servidor Linux com cron, por exemplo (troque os caminhos pelos da instalação):

```cron
* * * * * cd /srv/tvtec-agenda && /srv/tvtec-agenda/.venv/bin/python manage.py send_booking_emails >> /srv/tvtec-agenda/email-worker.log 2>&1
```

No Windows, o Agendador de Tarefas pode executar o Python do ambiente virtual com os argumentos `manage.py send_booking_emails`, tendo a pasta do projeto como diretório inicial. Configure repetição e a opção de não iniciar outra instância se a anterior estiver executando. O computador deve permanecer ligado.

### 7. Validar o fluxo completo

Entre com um usuário autorizado e faça uma reserva de sala ou veículo. Confirme que ela aparece em Minhas reservas e que o e-mail chega ao responsável. Teste também dia todo. A nova tentativa da mesma solicitação não cria outra confirmação na fila. Reservas feitas antes da integração não recebem mensagens retroativas.

### Se não enviar

| Sintoma | O que conferir |
| --- | --- |
| MAIL_MODE incorreto | Troque file/smtp por resend no ambiente efetivo e reinicie. |
| Chave ausente ou autenticação recusada | Confira RESEND_API_KEY, validade e permissão de envio. |
| Remetente recusado | Confira se o domínio do remetente está verificado e autorizado pela chave. |
| Timeout/conexão recusada | A hospedagem precisa permitir saída para smtp.resend.com na porta 465. |
| Aceito, mas não recebido | Consulte a mensagem no painel Resend, rejeições, spam e limites da conta. |
| Reserva salva sem e-mail | Verifique a configuração e execute send_booking_emails; não refaça a reserva. |

Não foi feita conexão autenticada nem envio real no ambiente entregue, pois a chave e o domínio verificado não foram fornecidos.

Fontes: [SMTP oficial](https://resend.com/docs/send-with-smtp), [domínios](https://resend.com/docs/dashboard/domains/introduction), [chaves de API](https://resend.com/docs/dashboard/api-keys/introduction).

## Referência da integração

1. No Resend, adicione um domínio de envio e configure no DNS os registros apresentados pelo painel. Aguarde a verificação.
2. Crie uma chave de API com permissão de envio para esse domínio.
3. Configure no ambiente do servidor (não no JavaScript nem no GitHub):

```dotenv
MAIL_MODE=resend
RESEND_API_KEY=preencha-no-servidor
DEFAULT_FROM_EMAIL=TVTEC Agenda <agenda@seu-dominio-verificado.br>
PUBLIC_URL=https://endereco-da-agenda
```

4. Execute `python manage.py migrate`, `python manage.py collectstatic --noinput` e reinicie a aplicação.
5. Agende no servidor `python manage.py send_booking_emails` a cada minuto, usando o mesmo ambiente e banco da aplicação. Esse comando recupera confirmações pendentes após falhas ou reinícios.
6. Faça uma reserva com uma conta autorizada, confira o destinatário e o recebimento. Confira também os logs de envio no painel Resend. Nenhum e-mail real foi enviado na validação local.

A integração usa o SMTP oficial Resend em `smtp.resend.com:465`, com SSL, usuário `resend` e a chave como senha. Convites e recuperação de senha também usam esse provedor quando MAIL_MODE=resend.

Cada nova reserva gera uma confirmação para o responsável autenticado, com recurso, datas, horários de Brasília e finalidade. Veículos incluem condutor, destino e orientação de abastecimento. Alterações, cancelamentos e bloqueios não geram uma nova confirmação de criação.

A confirmação é persistida na mesma transação da reserva e enviada após a gravação. Repetir a mesma solicitação não cria outro e-mail. Falhas não desfazem a reserva e ficam pendentes. `sent_at` indica aceitação SMTP, não confirmação de entrega na caixa; verifique rejeições e entrega no painel Resend. SMTP não garante envio único se o processo cair após o provedor aceitar e antes de registrar o resultado: nesse caso uma repetição é possível.

Referências oficiais: https://resend.com/changelog/smtp-service e https://resend.com/django
