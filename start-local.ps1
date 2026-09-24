$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) { $runtime = $pythonCommand.Source } else {
    $runtime = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (-not (Test-Path -LiteralPath $runtime)) { throw 'Instale Python 3.11 ou mais recente.' }
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $runtime -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível preparar o ambiente Python.' }
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível instalar as dependências.' }
}
& '.\.venv\Scripts\python.exe' setup_local.py
& '.\.venv\Scripts\python.exe' manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Falha nas migrations.' }
& '.\.venv\Scripts\python.exe' manage.py runserver 127.0.0.1:8765
