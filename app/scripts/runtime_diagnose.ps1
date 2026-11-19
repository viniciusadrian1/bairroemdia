param([ValidateRange(1024,65535)][int]$ApiPort = 8000, [ValidateRange(1024,65535)][int]$UiPort = 8502, [switch]$Docker, [string]$Python = 'python')
$ErrorActionPreference = 'Stop'
& $Python (Join-Path $PSScriptRoot 'runtime_manager.py') status --api-port $ApiPort --ui-port $UiPort
if ($Docker) {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        docker compose -f (Join-Path $PSScriptRoot '../../docker-compose.yml') config --quiet
        docker info --format '{{.ServerVersion}}'
    }
    if (Get-Command wsl -ErrorAction SilentlyContinue) { wsl --status; wsl --list --verbose }
}
