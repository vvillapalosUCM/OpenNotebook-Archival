. "$PSScriptRoot\Common.ps1"

try {
    Write-Section "Comprobando requisitos"
    Assert-RequiredFile $script:ComposePath "El archivo docker-compose de Windows"
    Assert-RequiredFile $script:EnvTemplatePath "La plantilla de entorno"
    Assert-Docker
    Write-Ok "Docker Desktop está disponible"

    Write-Section "Preparando configuración"
    $settings = Ensure-EnvFile

    if ([string]::IsNullOrWhiteSpace([string]$settings["OPEN_NOTEBOOK_PASSWORD"])) {
        do {
            $pwd = Read-Host "Introduzca la contraseña inicial de la herramienta"
            if ($pwd.Length -lt 10) {
                Write-Warn "La contraseña debe tener al menos 10 caracteres."
            }
        } while ($pwd.Length -lt 10)
        $settings["OPEN_NOTEBOOK_PASSWORD"] = $pwd
    } else {
        $settings["OPEN_NOTEBOOK_PASSWORD"] = Prompt-Value "Contraseña de acceso" $settings["OPEN_NOTEBOOK_PASSWORD"]
    }

    $hostOllama = Prompt-Value "URL local de Ollama (vista desde este ordenador)" $settings["HOST_OLLAMA_URL"]
    $settings["HOST_OLLAMA_URL"] = $hostOllama
    $settings["OLLAMA_API_BASE"] = Convert-HostUrlToContainerUrl $hostOllama

    $settings["FRONTEND_PORT"] = Prompt-Value "Puerto del frontend" $settings["FRONTEND_PORT"]
    $settings["API_PORT"] = Prompt-Value "Puerto de la API" $settings["API_PORT"]
    $settings["SURREAL_PORT"] = Prompt-Value "Puerto de la base de datos" $settings["SURREAL_PORT"]

    $settings["OPEN_NOTEBOOK_ALLOWED_ORIGINS"] = ("http://localhost:{0},http://127.0.0.1:{0}" -f $settings["FRONTEND_PORT"])
    Save-EnvFile $settings $script:EnvPath
    Show-Summary $settings

    Write-Section "Comprobando puertos"
    foreach ($entry in @(
        @{ Name = "Frontend"; Port = [int]$settings["FRONTEND_PORT"] },
        @{ Name = "API"; Port = [int]$settings["API_PORT"] },
        @{ Name = "SurrealDB"; Port = [int]$settings["SURREAL_PORT"] }
    )) {
        if (Get-ListeningState $entry.Port) {
            Write-Warn ("El puerto {0} ({1}) parece estar ocupado." -f $entry.Port, $entry.Name)
        } else {
            Write-Ok ("El puerto {0} ({1}) está libre." -f $entry.Port, $entry.Name)
        }
    }

    Write-Section "Construyendo y arrancando"
    Invoke-Compose @("up", "-d", "--build")

    Write-Section "Esperando a que la aplicación quede lista"
    Wait-ForAppReady -Settings $settings

    Write-Section "Comprobando Ollama"
    $ollamaTest = Test-HttpUrl ("{0}/api/tags" -f $settings["HOST_OLLAMA_URL"].TrimEnd('/'))
    if ($ollamaTest.Success) {
        Write-Ok ("Ollama responde correctamente en {0}" -f $settings["HOST_OLLAMA_URL"])
    } else {
        Write-Warn ("No se ha podido comprobar Ollama ahora mismo: {0}" -f $ollamaTest.Message)
        Write-Warn "La aplicación puede arrancar igualmente, pero las funciones de IA local no responderán hasta que Ollama esté en marcha."
    }

    Write-Section "Instalación finalizada"
    Write-Ok ("Abra la herramienta en http://localhost:{0}" -f $settings["FRONTEND_PORT"])
    Write-Info "La configuración se ha guardado en deployment\windows\runtime\settings.env"
    Open-App $settings
} catch {
    Write-Fail $_.Exception.Message
    exit 1
} finally {
    Pause-IfInteractive
}
