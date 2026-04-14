. "$PSScriptRoot\Common.ps1"

function ConvertFrom-SecureToPlainText([System.Security.SecureString]$SecureValue) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Read-SecretValue([string]$Prompt) {
    $secure = Read-Host $Prompt -AsSecureString
    return ConvertFrom-SecureToPlainText $secure
}

function Test-PasswordPolicy([string]$Password) {
    if ([string]::IsNullOrWhiteSpace($Password)) { return $false }
    if ($Password.Length -lt 12) { return $false }
    if ($Password -notmatch '[A-Z]') { return $false }
    if ($Password -notmatch '[a-z]') { return $false }
    if ($Password -notmatch '\d') { return $false }
    return $true
}

try {
    Write-Section "Comprobando requisitos"
    Assert-RequiredFile $script:ComposePath "El archivo docker-compose de Windows"
    Assert-RequiredFile $script:EnvTemplatePath "La plantilla de entorno"
    Assert-Docker
    Write-Ok "Docker Desktop está disponible"

    Write-Section "Preparando configuración"
    $settings = Ensure-EnvFile

    Write-Warn "La contraseña de acceso se guardará en deployment\windows\runtime\settings.env para que Docker Compose pueda arrancar la aplicación."

    if ([string]::IsNullOrWhiteSpace([string]$settings["OPEN_NOTEBOOK_PASSWORD"])) {
        do {
            $pwd = Read-SecretValue "Introduzca la contraseña inicial de la herramienta"
            if (-not (Test-PasswordPolicy $pwd)) {
                Write-Warn "La contraseña debe tener al menos 12 caracteres, con mayúsculas, minúsculas y dígitos."
            }
        } while (-not (Test-PasswordPolicy $pwd))
        $settings["OPEN_NOTEBOOK_PASSWORD"] = $pwd
    } else {
        $changePassword = Read-Host "Ya existe una contraseña configurada. ¿Desea cambiarla? (s/N)"
        if ($changePassword.Trim().ToLower() -in @("s", "si", "sí", "y", "yes")) {
            do {
                $pwd = Read-SecretValue "Introduzca la nueva contraseña de la herramienta"
                if (-not (Test-PasswordPolicy $pwd)) {
                    Write-Warn "La contraseña debe tener al menos 12 caracteres, con mayúsculas, minúsculas y dígitos."
                }
            } while (-not (Test-PasswordPolicy $pwd))
            $settings["OPEN_NOTEBOOK_PASSWORD"] = $pwd
        }
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
