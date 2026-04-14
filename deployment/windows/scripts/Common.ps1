Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:WindowsDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$script:RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $script:WindowsDir "..\.."))
$script:RuntimeDir = Join-Path $script:WindowsDir "runtime"
$script:EnvTemplatePath = Join-Path $script:WindowsDir "env.template"
$script:EnvPath = Join-Path $script:RuntimeDir "settings.env"
$script:ComposePath = Join-Path $script:WindowsDir "docker-compose.windows.local.yml"
$script:BackupsDir = Join-Path $script:WindowsDir "backups"
$script:DiagnosticsPath = Join-Path $script:RuntimeDir "diagnostico.txt"

function Write-Section([string]$Text) {
    Write-Host ""
    Write-Host "==== $Text ====" -ForegroundColor Cyan
}

function Write-Info([string]$Text) {
    Write-Host "[INFO] $Text" -ForegroundColor Gray
}

function Write-Ok([string]$Text) {
    Write-Host "[OK] $Text" -ForegroundColor Green
}

function Write-Warn([string]$Text) {
    Write-Host "[AVISO] $Text" -ForegroundColor Yellow
}

function Write-Fail([string]$Text) {
    Write-Host "[ERROR] $Text" -ForegroundColor Red
}

function Pause-IfInteractive {
    if ($Host.Name -notlike "*ServerRemoteHost*") {
        Write-Host ""
        Read-Host "Pulse ENTER para continuar"
    }
}

function Ensure-Directories {
    foreach ($path in @(
        $script:RuntimeDir,
        $script:BackupsDir,
        (Join-Path $script:RuntimeDir "surreal_data"),
        (Join-Path $script:RuntimeDir "notebook_data")
    )) {
        if (-not (Test-Path $path)) {
            New-Item -ItemType Directory -Path $path | Out-Null
        }
    }
}

function Load-EnvFile([string]$Path) {
    $map = [ordered]@{}
    if (-not (Test-Path $Path)) {
        return $map
    }

    foreach ($line in Get-Content -Path $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith('#')) {
            continue
        }

        $idx = $trimmed.IndexOf('=')
        if ($idx -lt 1) {
            continue
        }

        $key = $trimmed.Substring(0, $idx).Trim()
        $value = $trimmed.Substring($idx + 1)
        $map[$key] = $value
    }

    return $map
}

function Save-EnvFile($Map, [string]$Path) {
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("# Archivo generado por Open ArchiBook LLM")
    $lines.Add("# Puede editarlo si necesita cambiar puertos, password o endpoints")
    foreach ($entry in $Map.GetEnumerator()) {
        $lines.Add("$($entry.Key)=$($entry.Value)")
    }
    Set-Content -Path $Path -Value $lines -Encoding UTF8
}

function Set-IfMissing($Map, [string]$Key, [string]$Value) {
    if ((-not ($Map.Keys -contains $Key)) -or [string]::IsNullOrWhiteSpace([string]$Map[$Key])) {
        $Map[$Key] = $Value
    }
}

function New-RandomSecret([int]$Length = 48) {
    $chars = @()
    $chars += 48..57
    $chars += 65..90
    $chars += 97..122
    return -join ((1..$Length) | ForEach-Object { [char]($chars | Get-Random) })
}

function Convert-HostUrlToContainerUrl([string]$Url) {
    try {
        $uri = [Uri]$Url
        if ($uri.Host -in @("localhost", "127.0.0.1")) {
            return "{0}://host.docker.internal:{1}" -f $uri.Scheme, $uri.Port
        }
        return $Url
    } catch {
        return $Url
    }
}

function Ensure-EnvFile {
    Ensure-Directories

    if (-not (Test-Path $script:EnvPath)) {
        Copy-Item $script:EnvTemplatePath $script:EnvPath -Force
    }

    $settings = Load-EnvFile $script:EnvPath

    Set-IfMissing $settings "APP_NAME" "Open ArchiBook LLM"
    Set-IfMissing $settings "FRONTEND_PORT" "8502"
    Set-IfMissing $settings "API_PORT" "5055"
    Set-IfMissing $settings "SURREAL_PORT" "8000"
    Set-IfMissing $settings "SURREAL_ROOT_USER" "open_notebook"
    Set-IfMissing $settings "SURREAL_NAMESPACE" "open_notebook"
    Set-IfMissing $settings "SURREAL_DATABASE" "open_notebook"
    Set-IfMissing $settings "OPEN_NOTEBOOK_ALLOWED_ORIGINS" "http://localhost:8502,http://127.0.0.1:8502"
    Set-IfMissing $settings "OPEN_NOTEBOOK_PUBLIC_DOCS" "false"
    Set-IfMissing $settings "OPEN_NOTEBOOK_ENABLE_UPDATE_CHECK" "false"
    Set-IfMissing $settings "OPEN_NOTEBOOK_TRUST_PROXY_HEADERS" "false"
    Set-IfMissing $settings "OPEN_NOTEBOOK_AUTH_MAX_ATTEMPTS" "10"
    Set-IfMissing $settings "OPEN_NOTEBOOK_AUTH_WINDOW_SECONDS" "300"
    Set-IfMissing $settings "OPEN_NOTEBOOK_AUTH_BLOCK_SECONDS" "600"
    Set-IfMissing $settings "OPEN_NOTEBOOK_AUTH_FAILURE_DELAY_MS" "400"
    Set-IfMissing $settings "OPEN_NOTEBOOK_MAX_UPLOAD_BYTES" "52428800"
    Set-IfMissing $settings "OPEN_NOTEBOOK_ALLOW_PRIVATE_SOURCE_URLS" "false"
    Set-IfMissing $settings "HOST_OLLAMA_URL" "http://localhost:11434"
    Set-IfMissing $settings "OLLAMA_API_BASE" "http://host.docker.internal:11434"
    Set-IfMissing $settings "OPENAI_COMPATIBLE_BASE_URL" ""
    Set-IfMissing $settings "OPENAI_COMPATIBLE_API_KEY" ""

    if ([string]::IsNullOrWhiteSpace([string]$settings["OPEN_NOTEBOOK_ENCRYPTION_KEY"])) {
        $settings["OPEN_NOTEBOOK_ENCRYPTION_KEY"] = New-RandomSecret
    }

    if ([string]::IsNullOrWhiteSpace([string]$settings["SURREAL_ROOT_PASSWORD"])) {
        $settings["SURREAL_ROOT_PASSWORD"] = New-RandomSecret
    }

    Save-EnvFile $settings $script:EnvPath
    return $settings
}

function Assert-RequiredFile([string]$Path, [string]$FriendlyName) {
    if (-not (Test-Path $Path)) {
        throw "$FriendlyName no existe: $Path"
    }
}

function Assert-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker Desktop no está instalado o no está en PATH."
    }

    try {
        docker version | Out-Null
    } catch {
        throw "Docker Desktop parece no estar iniciado. Ábralo y vuelva a intentarlo."
    }
}

function Assert-Git {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git no está instalado o no está en PATH."
    }
}

function Invoke-Compose([string[]]$Args) {
    Push-Location $script:WindowsDir
    try {
        & docker compose --env-file $script:EnvPath -f $script:ComposePath @Args
    } finally {
        Pop-Location
    }
}

function Invoke-ComposeCapture([string[]]$Args) {
    Push-Location $script:WindowsDir
    try {
        return & docker compose --env-file $script:EnvPath -f $script:ComposePath @Args 2>&1
    } finally {
        Pop-Location
    }
}

function Get-ListeningState([int]$Port) {
    try {
        $result = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop
        return ($null -ne $result)
    } catch {
        return $false
    }
}

function Test-HttpUrl([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return [ordered]@{ Success = $true; StatusCode = $response.StatusCode; Message = "OK" }
    } catch {
        return [ordered]@{ Success = $false; StatusCode = ""; Message = $_.Exception.Message }
    }
}

function Open-App($Settings) {
    $url = "http://localhost:{0}" -f $Settings["FRONTEND_PORT"]
    Start-Process $url | Out-Null
}

function Prompt-Value([string]$Label, [string]$CurrentValue, [switch]$AllowEmpty) {
    if ($AllowEmpty) {
        $answer = Read-Host "$Label [$CurrentValue]"
        if ([string]::IsNullOrWhiteSpace($answer)) {
            return $CurrentValue
        }
        return $answer.Trim()
    }

    do {
        $answer = Read-Host "$Label [$CurrentValue]"
        if ([string]::IsNullOrWhiteSpace($answer)) {
            $answer = $CurrentValue
        }
        $answer = $answer.Trim()
    } while ([string]::IsNullOrWhiteSpace($answer))

    return $answer
}

function Show-Summary($Settings) {
    Write-Host ""
    Write-Host "Resumen de configuración" -ForegroundColor Cyan
    Write-Host ("- URL de la aplicación: http://localhost:{0}" -f $Settings["FRONTEND_PORT"])
    Write-Host ("- URL local de Ollama: {0}" -f $Settings["HOST_OLLAMA_URL"])
    Write-Host ("- URL de Ollama para Docker: {0}" -f $Settings["OLLAMA_API_BASE"])
    Write-Host ("- Archivo de configuración: {0}" -f $script:EnvPath)
}

function Get-ServiceStatusMap {
    $map = @{}
    $lines = Invoke-ComposeCapture @("ps", "--format", "json")
    foreach ($line in $lines) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try {
            $item = $line | ConvertFrom-Json
            $map[$item.Service] = $item
        } catch {
        }
    }
    return $map
}

function Get-ServiceLogsText([string]$Service, [int]$Tail = 80) {
    $lines = Invoke-ComposeCapture @("logs", "--tail", "$Tail", $Service)
    return ($lines -join [Environment]::NewLine)
}

function Wait-ForAppReady($Settings, [int]$MaxAttempts = 18, [int]$DelaySeconds = 5) {
    $frontendUrl = "http://localhost:{0}" -f $Settings["FRONTEND_PORT"]
    $healthUrl = "http://localhost:{0}/health" -f $Settings["API_PORT"]

    for ($i = 1; $i -le $MaxAttempts; $i++) {
        $services = Get-ServiceStatusMap
        $apiOk = (Test-HttpUrl $healthUrl).Success
        $frontendOk = (Test-HttpUrl $frontendUrl).Success

        $openNotebookStatus = if ($services.ContainsKey("open_notebook")) { [string]$services["open_notebook"].State } else { "desconocido" }
        $surrealStatus = if ($services.ContainsKey("surrealdb")) { [string]$services["surrealdb"].State } else { "desconocido" }

        Write-Info ("Comprobación {0}/{1}: API={2}, Frontend={3}, open_notebook={4}, surrealdb={5}" -f `
            $i, $MaxAttempts, ($(if ($apiOk) { "OK" } else { "FALLO" })), ($(if ($frontendOk) { "OK" } else { "FALLO" })), $openNotebookStatus, $surrealStatus)

        if ($apiOk -and $frontendOk -and $openNotebookStatus -eq "running" -and $surrealStatus -eq "running") {
            Write-Ok "La aplicación ha arrancado correctamente."
            return
        }

        Start-Sleep -Seconds $DelaySeconds
    }

    $serviceMap = Get-ServiceStatusMap
    $openNotebookStatus = if ($serviceMap.ContainsKey("open_notebook")) { [string]$serviceMap["open_notebook"].State } else { "no encontrado" }
    $surrealStatus = if ($serviceMap.ContainsKey("surrealdb")) { [string]$serviceMap["surrealdb"].State } else { "no encontrado" }

    $openNotebookLogs = Get-ServiceLogsText -Service "open_notebook" -Tail 120
    $surrealLogs = Get-ServiceLogsText -Service "surrealdb" -Tail 60

    $message = @"
La aplicación no ha quedado lista después de varias comprobaciones.

Estado observado:
- open_notebook: $openNotebookStatus
- surrealdb: $surrealStatus

Últimas líneas de open_notebook:
$openNotebookLogs

Últimas líneas de surrealdb:
$surrealLogs
"@

    throw $message
}

Export-ModuleMember -Function * -Variable WindowsDir, RepoRoot, RuntimeDir, EnvTemplatePath, EnvPath, ComposePath, BackupsDir, DiagnosticsPath
