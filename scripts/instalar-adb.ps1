<#
.SYNOPSIS
  Baixa o ADB oficial do Google (Android SDK Platform-Tools) para a pasta platform-tools\ do projeto.
  Não precisa de administrador e não mexe no PATH do sistema.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\instalar-adb.ps1
#>
$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $PSScriptRoot
$Destino = Join-Path $Raiz 'platform-tools'
$Url = 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip'

if (Test-Path (Join-Path $Destino 'adb.exe')) {
    Write-Host "ADB já está em $Destino" -ForegroundColor Green
    & (Join-Path $Destino 'adb.exe') version
    exit 0
}

$zip = Join-Path $env:TEMP 'platform-tools-tablet-kit.zip'
Write-Host "Baixando de $Url ..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $Url -OutFile $zip -UseBasicParsing

Write-Host 'Extraindo...'
Expand-Archive -Path $zip -DestinationPath $Raiz -Force
Remove-Item $zip -Force

$adb = Join-Path $Destino 'adb.exe'
$sig = Get-AuthenticodeSignature $adb
if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'Google') {
    Write-Host "ATENÇÃO: a assinatura digital do adb.exe não é do Google ($($sig.Status)). Apague a pasta platform-tools e baixe manualmente em https://developer.android.com/tools/releases/platform-tools" -ForegroundColor Red
    exit 1
}
Write-Host "OK ADB instalado em $Destino (assinado por Google)" -ForegroundColor Green
& $adb version
