. "$PSScriptRoot\Common.ps1"
try {
    Write-Section "Comprobando requisitos"
    Assert-RequiredFile $script:ComposePath "El archivo docker-compose de Windows"
    Assert-Docker
    $settings = Ensure-EnvFile
    Write-Section "Arrancando servicios"
    Invoke-Compose @("up", "-d")
    Write-Ok ("Aplicación disponible en http://localhost:{0}" -f $settings["FRONTEND_PORT"])
    Open-App $settings
} catch {
    Write-Fail $_.Exception.Message
    exit 1
} finally {
    Pause-IfInteractive
}
