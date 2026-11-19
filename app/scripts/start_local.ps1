param(
    [switch]$WithModels,
    [ValidateRange(1024,65535)][int]$ApiPort = 8000,
    [ValidateRange(1024,65535)][int]$UiPort = 8502,
    [string]$EnvFile,
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
if (-not $PSBoundParameters.ContainsKey('Python')) {
    $projectPython = Join-Path (Split-Path -Parent $PSScriptRoot) '.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $projectPython -PathType Leaf) { $Python = $projectPython }
}
$runtimeArgs = @((Join-Path $PSScriptRoot 'runtime_manager.py'), 'start', '--api-port', "$ApiPort", '--ui-port', "$UiPort")
if ($WithModels) { $runtimeArgs += '--with-models' }
if ($EnvFile) { $runtimeArgs += @('--env-file', $EnvFile) }
& $Python @runtimeArgs
if ($LASTEXITCODE -ne 0) { throw "Inicializacao falhou. Consulte a mensagem acima e os logs em app/runtime." }
