param([ValidateRange(1024,65535)][int]$ApiPort = 8000, [ValidateRange(1024,65535)][int]$UiPort = 8502, [string]$Python = 'python')
$ErrorActionPreference = 'Stop'
& $Python (Join-Path $PSScriptRoot 'runtime_manager.py') stop --api-port $ApiPort --ui-port $UiPort
if ($LASTEXITCODE -ne 0) { throw 'Falha ao parar os processos registrados.' }
