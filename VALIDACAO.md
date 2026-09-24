# Validação — atualização de 24/09/2026

## Resend e revisão visual

- Suíte completa: **40 testes aprovados**, em 175,678 segundos, com SQLite e e-mail em memória.
- Novos testes: envio após commit ao responsável, repetição idempotente, falha de entrega preservando a reserva, reenvio pendente, rollback sem mensagem e conflito sem outra confirmação.
- Nome da sala 2 atualizado para corredor rádio, mantendo o mesmo recurso e reservas.
- Hierarquia de nomes, corredores e capacidades revisada em cartões e navegação; contraste e espaçamento melhorados.
- Consulta de disponibilidade até meia-noite corrigida para exibir 24:00.
- Verificação visual em layouts de desktop e celular; largura do conteúdo igual à largura disponível, sem rolagem horizontal nos cenários observados.
- Resend preparado pela API HTTPS. A chave não está configurada e não foi realizado envio externo: ativação e teste real seguem RESEND.md.
- A fila precisa do comando send_booking_emails agendado no servidor para recuperar falhas. A API usa chave de idempotência, mas a aceitação pelo provedor não é confirmação de entrega na caixa.
- PostgreSQL e entrega real no provedor ainda não foram validados. Os testes aprovados não garantem ausência de todos os erros.

## Revisão atual

- Executada a suíte de 35 testes em SQLite: 34 passaram; um teste de desativação usava nome incompleto após a adoção da regra de nome completo.
- Corrigido esse dado de teste; o teste de desativação e o teste de provisionamento foram reexecutados e passaram (2/2).
- Adicionado e aprovado um teste de consulta de reserva de dia todo por outro colaborador, verificando também que os campos privados não são expostos (1/1).
- `manage.py check`: nenhum problema; `makemigrations --check --dry-run`: nenhuma alteração; `node --check static/app.js`: aprovado.
- Corrigido o contraste do número do dia atual quando há ocupações. O destaque de reservas permanece em azul na grade e lista diária.
- O provisionamento de uma nova base inclui o nome Witter Veloso no administrador inicial.
- Corrigida a identificação SQL da coluna `end` na restrição PostgreSQL. PostgreSQL não foi executado neste ambiente: implantação e concorrência de operações administrativas ainda exigem validação nesse banco.
- O ZIP atualizado exclui banco, arquivos de e-mail, `.env`, ambiente virtual e caches. A conta local não acompanha o pacote.

Os resultados abaixo são o registro histórico da validação anterior; não representam uma nova execução completa após as alterações acima.

# Validação anterior — 23/09/2026

## Testes automatizados

**35 testes aprovados** (`python manage.py test --verbosity 1`, 129,065 segundos na execução completa). `manage.py check`: nenhum problema. `makemigrations --check --dry-run`: nenhuma alteração pendente.

Cobertura de comportamento:

- Autenticação obrigatória, CSRF, ausência de cadastro público e impedimento de promoção por colaborador.
- Permissões por perfil e tipo de recurso, incluindo revalidação de administrador cuja permissão mudou.
- Edição/cancelamento alheios proibidos para colaborador; usuário desativado perde sessão e acesso de escrita.
- Proteção do último administrador ativo.
- Sobreposição proibida; recursos diferentes e horários consecutivos permitidos.
- Trigger de INSERT e UPDATE protege a integridade mesmo em escrita direta.
- Corrida real com duas conexões SQLite independentes, em arquivo temporário e sincronizadas por barreira: exatamente uma gravação e um conflito.
- Reservas e bloqueios compartilham a proteção de conflito.
- Cancelamento libera disponibilidade e preserva registros/auditoria.
- Edição validada contra conflito e versão antiga rejeitada.
- Salas: início 06h00 permitido, início antes disso recusado, slots de 30 minutos, duração mínima, exceção 23h59 e proibição de cruzar meia-noite.
- Veículos: retorno após meia-noite, dia todo 00h00–00h00 no fuso institucional e conflito com ocupação parcial.
- Campos privados removidos da resposta para outros colaboradores.
- Repetição idempotente e recusa de reutilização da mesma chave com outro conteúdo.
- Novas reservas no passado recusadas; correção administrativa de reserva anterior com justificativa permitida.
- Desativação de usuário exige decisão explícita sobre reservas; alteração de recurso com reservas afetadas é recusada.
- Períodos de veículos não são presumidos e o intervalo configurado é validado.
- Limitação de tentativas de autenticação.
- Convite individual em e-mail de teste, senha segura, conta só ativa após verificação, token de uso único e convite expirado.
- Recuperação de senha e revogação de sessões antigas.
- Provisionamento do administrador inicial não ativa a conta nem cria senha padrão.
- Inicialização idempotente dos recursos e leitura persistida em uma nova sessão.
- Próxima ocupação além de 30 dias aparece na visão geral.
- Datas sem offset são interpretadas no fuso institucional.

Os testes de e-mail utilizam caixa em memória. Nenhum e-mail real foi enviado. A concorrência real foi validada no mecanismo transacional do banco; não foi feito ensaio de carga distribuída.

## Navegador

Validação manual assistida em navegador Chromium integrado, com conta fictícia e banco isolado da base real:

- Login; exibição do logotipo fornecido; visão geral com cinco recursos.
- Reserva de sala de 30 minutos; confirmação; recarregamento completo e consulta em Minhas reservas mantendo o registro.
- Edição da reserva, dois acréscimos de 30 minutos e persistência do novo término.
- Seleção de Veículos abre calendário mensal.
- Em viewport de 390 × 844: navegação compacta, lista diária, formulário, lista de reservas e telas administrativas.
- Configuração de manhã/tarde do Gol (exclusivo jornalismo) no banco de teste; seleção do período apresenta o intervalo configurado.
- Reserva de veículo de 23h30 até 01h30 seguinte; resumo explícito das datas; registro preservado após recarregar.
- Conflito de reserva: mensagem com intervalo ocupado, título preservado no formulário, alternativa 10h30 sugerida; escolha e gravação do horário consecutivo.
- Lista de usuários e acesso à configuração de recursos pelo celular.
- Ausência de rolagem horizontal da página no viewport móvel verificado (`scrollWidth = clientWidth = 375`, largura interna após barra de rolagem).

A base de teste fica fora do projeto, em `work/qa.sqlite3`; não integra o ZIP. Não há usuário de teste inicializado automaticamente. A prévia de teste apresenta um aviso explícito no topo. A aplicação real usa outra base, contendo apenas os cinco recursos e nenhuma conta ativa.

## Limites reais

- SMTP institucional não configurado: entrega externa de convites e recuperação ainda precisa ser ativada e testada.
- Administrador institucional ainda não provisionado/ativado; procedimento completo em `README.md`.
- Hospedagem, domínio HTTPS e backups de produção não foram fornecidos nem implantados.
- Os períodos dos veículos permanecem sem definição na base real, aguardando decisão administrativa.
- Não foram testados Safari, Firefox ou aparelhos físicos. A validação móvel usa viewport responsivo de Chromium.
- A visualização depende de JavaScript. Não há reservas offline; o banco no servidor é a fonte de verdade.
