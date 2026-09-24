"""Prepara somente desenvolvimento. Não cria usuários nem popula reservas."""
import secrets
from pathlib import Path
base=Path(__file__).resolve().parent
(base/'data').mkdir(exist_ok=True)
path=base/'.env'
if path.exists():
    print('.env existente preservado.')
else:
    path.write_text('SECRET_KEY='+secrets.token_urlsafe(64)+'\nDEBUG=1\nMAIL_MODE=file\nALLOWED_HOSTS=localhost,127.0.0.1\nPUBLIC_URL=http://127.0.0.1:8765\n',encoding='utf-8')
    print('Configuração local criada com segredo aleatório. E-mails serão gravados em data/emails, sem envio real.')
