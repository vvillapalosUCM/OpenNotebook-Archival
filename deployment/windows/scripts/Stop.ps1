. "$PSScriptRoot\Common.ps1"
try {
    Write-Section "Apagando servicios"
    Assert-RequiredFile $script:ComposePath "El archivo docker-compose de Windows"
    Assert-Docker
    $null = Ensure-EnvFile
    Invoke-Compose @("down")
    Write-Ok "La herramienta se ha apagado correctamente."
} catch {
    Write-Fail $_.Exception.Message
    exit 1
} finally {
    Pause-IfInteractive
}
