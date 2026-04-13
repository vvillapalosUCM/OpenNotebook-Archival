. "$PSScriptRoot\Common.ps1"

try {
    Write-Section "Comprobando requisitos"
    Assert-RequiredFile $script:ComposePath "El archivo docker-compose de Windows"
    Assert-Docker
    Assert-Git
    $settings = Ensure-EnvFile

    Write-Section "Actualizando repositorio"
    Push-Location $script:RepoRoot
    try {
        git pull --ff-only
    } finally {
        Pop-Location
    }

    Write-Section "Reconstruyendo y arrancando"
    Invoke-Compose @("up", "-d", "--build")

    Write-Section "Esperando a que la aplicación quede lista"
    Wait-ForAppReady -Settings $settings

    Write-Ok ("Actualización completada. Aplicación disponible en http://localhost:{0}" -f $settings["FRONTEND_PORT"])
    Open-App $settings
} catch {
    Write-Fail $_.Exception.Message
    Write-Warn "Puede ejecutar 06-DIAGNOSTICO.bat para generar un informe técnico."
    exit 1
} finally {
    Pause-IfInteractive
}
