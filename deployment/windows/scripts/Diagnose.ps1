. "$PSScriptRoot\Common.ps1"
$report = New-Object System.Collections.Generic.List[string]
function Add-Report([string]$Line) { $report.Add($Line) | Out-Null }

try {
    Write-Section "Diagnóstico"
    $settings = Ensure-EnvFile

    Add-Report "DIAGNÓSTICO OPEN ARCHIBOOK LLM"
    Add-Report ("Fecha: {0}" -f (Get-Date))
    Add-Report ("Repositorio: {0}" -f $script:RepoRoot)
    Add-Report ""

    if (Get-Command docker -ErrorAction SilentlyContinue) {
        Add-Report "Docker: INSTALADO"
        try {
            docker version | Out-Null
            Add-Report "Docker daemon: ACTIVO"
            Write-Ok "Docker Desktop está activo"
        } catch {
            Add-Report "Docker daemon: NO ACTIVO"
            Write-Warn "Docker Desktop parece no estar activo"
        }
    } else {
        Add-Report "Docker: NO INSTALADO"
        Write-Warn "Docker no está disponible en PATH"
    }

    Add-Report ("Compose Windows: {0}" -f (Test-Path $script:ComposePath))
    Add-Report ("Archivo settings.env: {0}" -f (Test-Path $script:EnvPath))
    Add-Report ("Frontend port: {0}" -f $settings["FRONTEND_PORT"])
    Add-Report ("API port: {0}" -f $settings["API_PORT"])
    Add-Report ("SurrealDB port: {0}" -f $settings["SURREAL_PORT"])
    Add-Report ""

    foreach ($entry in @(
        @{ Name = "Frontend"; Port = [int]$settings["FRONTEND_PORT"] },
        @{ Name = "API"; Port = [int]$settings["API_PORT"] },
        @{ Name = "SurrealDB"; Port = [int]$settings["SURREAL_PORT"] }
    )) {
        $busy = Get-ListeningState $entry.Port
        Add-Report ("Puerto {0} ({1}): {2}" -f $entry.Port, $entry.Name, ($(if ($busy) { "OCUPADO/ESCUCHANDO" } else { "LIBRE O CAÍDO" })))
    }

    $front = Test-HttpUrl ("http://localhost:{0}" -f $settings["FRONTEND_PORT"])
    $api = Test-HttpUrl ("http://localhost:{0}/health" -f $settings["API_PORT"])
    $ollama = Test-HttpUrl ("{0}/api/tags" -f $settings["HOST_OLLAMA_URL"].TrimEnd('/'))

    Add-Report ""
    Add-Report ("Frontend HTTP: {0} ({1})" -f ($(if ($front.Success) { "OK" } else { "FALLO" })), $front.Message)
    Add-Report ("API HTTP: {0} ({1})" -f ($(if ($api.Success) { "OK" } else { "FALLO" })), $api.Message)
    Add-Report ("Ollama HTTP: {0} ({1})" -f ($(if ($ollama.Success) { "OK" } else { "FALLO" })), $ollama.Message)

    if (Get-Command docker -ErrorAction SilentlyContinue) {
        Add-Report ""
        Add-Report "docker compose ps:"
        try {
            $composePs = & docker compose --env-file $script:EnvPath -f $script:ComposePath ps 2>&1
            foreach ($line in $composePs) { Add-Report $line }
        } catch {
            Add-Report ("No se ha podido ejecutar docker compose ps: {0}" -f $_.Exception.Message)
        }
    }

    Set-Content -Path $script:DiagnosticsPath -Value $report -Encoding UTF8
    Write-Ok ("Informe guardado en {0}" -f $script:DiagnosticsPath)
    Start-Process notepad.exe $script:DiagnosticsPath | Out-Null
} catch {
    Write-Fail $_.Exception.Message
    exit 1
} finally {
    Pause-IfInteractive
}
