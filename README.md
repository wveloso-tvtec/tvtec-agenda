# TVTEC Agenda

Aplicação de reservas de salas e veículos da Fundação Escola TVTEC Jundiaí. Interface em português do Brasil, backend Django 5.2, sessões no servidor e SQLite com proteção transacional de conflitos. O logotipo fornecido é usado sem modificar o arquivo original; o CSS recorta apenas o espaço branco ao redor.

## GitHub e execução real

Envie a pasta inteira do projeto para o GitHub. O arquivo HTML da interface está em `templates/index.html`, mas ele depende de `agenda/`, `config/`, migrations, banco e dos arquivos em `static/`; publicar somente o HTML em GitHub Pages não executará login, reservas ou persistência.

O `Procfile` incluído inicia o servidor WSGI em serviços que fornecem `PORT`. Antes de abrir o acesso institucional, configure `DEBUG=0`, `SECRET_KEY` exclusiva, `ALLOWED_HOSTS`, `PUBLIC_URL`, HTTPS, PostgreSQL e e-mail conforme a seção de produção. GitHub é o repositório do código, não o servidor da aplicação.

O projeto já aceita `DATABASE_URL` no formato `postgresql://...`; quando essa variável existe, ela substitui `DATABASE_PATH` e usa PostgreSQL com conexão persistente. O `build.sh` executa `collectstatic` e `migrate` durante o deploy.

## Iniciar localmente

Requer Python 3.11 ou superior. No Windows, execute `start-local.ps1` nesta pasta. O script cria um ambiente virtual, instala as versões verificadas, prepara um segredo aleatório, executa migrations e abre o servidor em http://127.0.0.1:8765. Ele não cria usuários ou reservas.

Alternativa manual, dentro desta pasta:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe setup_local.py
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8765
```

No Linux/macOS, use `.venv/bin/python` no lugar de `.venv\Scripts\python.exe`.

As migrations criam as tabelas, os triggers de integridade e, de forma idempotente, Sala de reunião 1 - corredor principal (até 4 pessoas), Sala de reunião 2 - corredor rádio (acima de 8 pessoas), Gol (exclusivo jornalismo), Parati (exclusivo jornalismo) e Spin. O banco padrão é `data/agenda.sqlite3`. `DATABASE_PATH` pode indicar outro arquivo absoluto. Preserve esse arquivo em volume persistente; não coloque SQLite em unidade de rede. Use um único servidor de aplicação para esta arquitetura. A migration inclui restrição de exclusão para PostgreSQL, mas a execução e a concorrência nessa plataforma ainda precisam de validação em um banco PostgreSQL real. Os testes realizados usam SQLite.

## Administrador inicial: ativação segura

1. Configure e teste o Resend e `PUBLIC_URL` no `.env`, conforme a seção seguinte.
2. Execute `python manage.py provision_admin` usando o Python do ambiente virtual.
3. O comando cria **wveloso@tvtecjundiai.com.br** como administrador pendente, sem senha utilizável, e envia um convite individual de 48 horas.
4. A pessoa proprietária dessa caixa de e-mail abre o link, verifica o e-mail e define sua própria senha (mínimo de 12 caracteres, validadores do Django).
5. Só depois da verificação a conta fica ativa. Não há senha padrão nem concessão de perfil baseada no e-mail informado no login.

Reexecutar o comando reenvia o convite pendente e invalida o anterior. Conta já verificada não é promovida ou alterada por esse procedimento. Novos administradores são geridos por outro administrador na aplicação. O último administrador ativo não pode ser desativado nem perder o perfil.

**O envio de convite para a caixa institucional ainda não foi validado.** A chave e o domínio verificado do Resend não foram fornecidos. O pacote distribuído não inclui a base local nem contas e senhas. A conta local de Witter Veloso não é transferida automaticamente ao servidor; provisione o administrador no banco da hospedagem.

## E-mails, convites e recuperação

Copie `.env.example` para uma configuração de implantação e preencha:

- `SECRET_KEY`: segredo aleatório exclusivo (por exemplo, `python -c "import secrets; print(secrets.token_urlsafe(64))"`).
- `PUBLIC_URL`: origem HTTPS definitiva, sem barra final. Os links enviados usam esta origem, nunca o cabeçalho Host do pedido.
- `ALLOWED_HOSTS`: nomes de host separados por vírgula, sem protocolo.
- `CSRF_TRUSTED_ORIGINS`: origens HTTPS autorizadas, separadas por vírgula.
- `MAIL_MODE=resend`, `RESEND_API_KEY` e `DEFAULT_FROM_EMAIL`; consulte RESEND.md.
- `DEBUG=0` em produção.

Convites: **Usuários e acessos → Convidar** ou **Gerenciar → Reenviar convite**. Convites expiram em 48 horas. Recuperação: **Esqueci minha senha**, na tela de acesso; links expiram em uma hora. Os tokens são aleatórios, armazenados somente por hash e invalidados após uso. Alterar a senha invalida sessões anteriores. Não há cadastro público.

`MAIL_MODE=file` é exclusivamente para desenvolvimento com `DEBUG=1`: grava mensagens em `data/emails`, sem enviar e-mail. Ler um arquivo local não comprova posse da caixa real. Esse modo é bloqueado em produção e não deve ser usado para ativar contas institucionais para operação real. Os testes automatizados usam backend de e-mail em memória. Entrega SMTP real, autenticação no provedor e recebimento na caixa institucional **não foram verificados**.

Não inclua `.env`, banco de dados ou mensagens locais em repositório/pacote. O ZIP de entrega exclui esses itens.

## Uso e administração

- **Visão geral:** situação atual e próxima ocupação dos cinco recursos; consulta diária em colunas, semanal ou mensal; filtros por tipo e recurso.
- **Salas:** semana no computador e lista diária no celular. Reservas em blocos de 30 minutos, 06h00–23h59 inicialmente, sem atravessar a meia-noite. Término 23h59 é aceito apenas mantendo a duração mínima de 30 minutos.
- **Veículos:** seleção de Gol (exclusivo jornalismo), Parati (exclusivo jornalismo) ou Spin abre o mês; trocar de carro preserva o mês. Por horas, por período ou dia todo; retorno posterior é permitido. Dia todo é 00h00 até 00h00 seguinte, em America/Sao_Paulo.
- **Períodos manhã e tarde:** **Recursos e configurações → veículo → Configurar**. Inicialmente ficam vazios e indisponíveis; não foram presumidos horários. São atalhos e não restringem o modo por horas.
- **Minhas reservas:** próximas, anteriores e canceladas. Colaboradores editam/cancelam apenas reservas próprias futuras. Administradores podem corrigir registros anteriores/em andamento com justificativa, preservando horários passados quando necessário.
- **Gestão de reservas:** filtro por intervalo, recurso, usuário e situação. Cancelamentos preservam registros e liberam o horário.
- **Usuários e acessos:** convite, reenvio, perfil, permissões por tipo de recurso, ativação/desativação. Ao desativar alguém com ocupações futuras/em andamento, o sistema mostra a lista e exige manter ou cancelar explicitamente. A lista é revalidada no momento da decisão.
- **Recursos e configurações:** nome, descrição, funcionamento, períodos, ativação e bloqueios. Redução de funcionamento/desativação com ocupações afetadas é recusada com a lista; é necessário resolver cada uma em Gestão de reservas e tentar novamente. Bloqueios conflitantes também são recusados.
- **Histórico de atividades:** autor, instante, entidade, antes/depois e justificativa. Não há endpoint para editar ou excluir auditoria.

## Integridade e segurança

SQLite usa transações `BEGIN IMMEDIATE`, serializando escrita e decisões de autorização. Dois triggers rejeitam sobreposição em INSERT e UPDATE de ocupações ativas do mesmo recurso. Reservas e bloqueios compartilham a tabela e a mesma proteção. Intervalos são `[início, término)`, permitindo horários consecutivos. A API também valida regras de domínio e fornece mensagens de conflito. Há chave idempotente por usuário na criação e versão por `updated` na edição.

Todos os acessos internos requerem sessão autenticada e conta ativa/verificada; permissões são verificadas no servidor. Campos privados só aparecem na resposta para o responsável ou administrador. Senhas usam os hashers e validadores do Django. Proteções: CSRF, cookies HttpOnly/SameSite, cookies Secure e HTTPS obrigatório fora do desenvolvimento, CSP, consultas parametrizadas pelo ORM e limitação de tentativas por IP e e-mail (janela de 15 minutos).

Datas são interpretadas/exibidas no fuso America/Sao_Paulo; persistência UTC com `USE_TZ`. A agenda atualiza a cada 20 segundos quando visível e sem formulário aberto. A validação transacional no salvamento é definitiva, mesmo se uma ocupação ainda não apareceu na consulta de outra pessoa.

## Testes

```powershell
.\.venv\Scripts\python.exe manage.py test --verbosity 2
.\.venv\Scripts\python.exe manage.py check
```

Veja `VALIDACAO.md` para resultados, cenários e limites. Testes usam bases isoladas. Nenhuma carga demonstrativa ocorre nas migrations ou na inicialização.

## Implantação

O ambiente entregue é local. Não foi publicado em um serviço externo. A arquitetura usa Python/Django, exigindo hospedagem compatível com WSGI e volume persistente; não é uma exportação estática nem uma aplicação para Cloudflare Workers/Sites.

Para produção, configure as variáveis acima, domínio/TLS e SMTP. Execute:

```powershell
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
waitress-serve --listen=127.0.0.1:8000 config.wsgi:application
```

Coloque um proxy HTTPS à frente do Waitress. Configure a informação de esquema do proxy de modo que Django receba `wsgi.url_scheme=https` somente de um proxy confiável; não confie indiscriminadamente em cabeçalhos enviados pelo cliente. Mantenha o servidor WSGI acessível apenas pelo proxy. O WhiteNoise serve arquivos estáticos coletados. Programe backup consistente do SQLite (API de backup SQLite ou backup com aplicação parada) e teste restauração. Execute `python manage.py clearsessions` periodicamente para remover sessões expiradas.

Pendências para operação institucional: configuração real do Resend e teste de entrega; escolha de hospedagem/domínio/TLS e backup; provisionamento do administrador no banco da hospedagem; definição dos períodos de manhã/tarde conforme decisão da instituição. Esses itens dependem de informações externas que não foram fornecidas.


## Confirmações pelo Resend

Consulte RESEND.md para configurar o remetente, a chave e o reenvio das confirmações pendentes.
