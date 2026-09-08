<#
    Instala MetaFlotPy como servicio de Windows usando NSSM.

    Requisitos:
      · Ejecutar PowerShell como Administrador
      · NSSM en el PATH o indicado con -Nssm  (https://nssm.cc/download)

    Uso:
        .\despliegue\windows\instalar-servicio.ps1
        .\despliegue\windows\instalar-servicio.ps1 -Puerto 8080 -Nssm C:\nssm\nssm.exe

    Desinstalar:
        .\despliegue\windows\instalar-servicio.ps1 -Desinstalar
#>
[CmdletBinding()]
param(
    [string]$Nombre = 'MetaFlotPy',
    [string]$Escucha = '127.0.0.1',
    [int]$Puerto = 8000,
    [int]$Hilos = 6,
    [string]$Venv = '',
    [string]$Nssm = 'nssm.exe',
    [string]$Registros = 'C:\ProgramData\MetaFlotPy\logs',
    [switch]$Desinstalar
)

$ErrorActionPreference = 'Stop'

function Requiere-Administrador {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Ejecuta esta consola de PowerShell como Administrador.'
    }
}
Requiere-Administrador

$nssmCmd = (Get-Command $Nssm -ErrorAction SilentlyContinue)
if (-not $nssmCmd) {
    throw "No se encontró NSSM. Descárgalo de https://nssm.cc/download y pásalo con -Nssm <ruta a nssm.exe>."
}
$Nssm = $nssmCmd.Source

# --- Desinstalación ---
if ($Desinstalar) {
    & $Nssm stop $Nombre confirm 2>$null
    & $Nssm remove $Nombre confirm
    Write-Host "Servicio '$Nombre' eliminado." -ForegroundColor Yellow
    return
}

$Raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

if (-not $Venv) {
    foreach ($ruta in @("$Raiz\.venv", "$Raiz\venv", (Split-Path -Parent $Raiz))) {
        if (Test-Path "$ruta\Scripts\waitress-serve.exe") { $Venv = $ruta; break }
    }
}
if (-not $Venv) { throw "No se encontró el entorno virtual. Indícalo con -Venv <ruta>." }

$Waitress = Join-Path $Venv 'Scripts\waitress-serve.exe'
$Python   = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Path $Waitress)) { throw "Falta waitress en $Venv (pip install -r requirements.txt)." }

# --- Clave de sesión persistente ---
$archivoEnv = Join-Path $Raiz '.env'
if (-not (Test-Path $archivoEnv)) {
    $clave = & $Python -c "import secrets; print(secrets.token_hex(32))"
    @(
        'METAFLOTPY_ENTORNO=produccion',
        "METAFLOTPY_SECRET_KEY=$clave",
        'METAFLOTPY_TRAS_PROXY=1'
    ) | Set-Content -Path $archivoEnv -Encoding utf8
    Write-Host "Archivo .env creado con una clave de sesión nueva." -ForegroundColor Green
}
$variables = Get-Content $archivoEnv | Where-Object { $_ -match '^\s*[A-Za-z_]' }

New-Item -ItemType Directory -Force -Path $Registros | Out-Null

# --- Alta del servicio ---
& $Nssm stop $Nombre confirm 2>$null
& $Nssm remove $Nombre confirm 2>$null

& $Nssm install $Nombre $Waitress
& $Nssm set $Nombre AppParameters "--listen=$Escucha`:$Puerto --threads=$Hilos --channel-timeout=90 wsgi:app"
& $Nssm set $Nombre AppDirectory $Raiz
& $Nssm set $Nombre DisplayName 'MetaFlotPy — cálculo metalúrgico'
& $Nssm set $Nombre Description 'Plataforma web de cálculos de procesamiento de minerales.'
& $Nssm set $Nombre Start SERVICE_AUTO_START
& $Nssm set $Nombre AppEnvironmentExtra $variables
& $Nssm set $Nombre AppStdout (Join-Path $Registros 'metaflotpy.out.log')
& $Nssm set $Nombre AppStderr (Join-Path $Registros 'metaflotpy.err.log')
& $Nssm set $Nombre AppRotateFiles 1
& $Nssm set $Nombre AppRotateBytes 10485760
& $Nssm set $Nombre AppExit Default Restart
& $Nssm set $Nombre AppRestartDelay 5000

& $Nssm start $Nombre
Start-Sleep -Seconds 4

# --- Comprobación ---
try {
    $r = Invoke-RestMethod -Uri "http://$Escucha`:$Puerto/salud" -TimeoutSec 10
    Write-Host ""
    Write-Host "Servicio '$Nombre' activo." -ForegroundColor Green
    Write-Host "  /salud -> estado=$($r.estado) version=$($r.version) entorno=$($r.entorno)"
} catch {
    Write-Warning "El servicio se instaló pero no respondió. Revisa $Registros\metaflotpy.err.log"
    throw
}

Write-Host ""
Write-Host "Siguientes pasos:" -ForegroundColor Cyan
Write-Host "  1. Configura Nginx o IIS como proxy inverso con HTTPS."
Write-Host "     Plantillas: despliegue\windows\nginx-metaflotpy.conf  y  web.config"
Write-Host "  2. Abre el puerto 443 en el firewall (el $Puerto queda solo local)."
Write-Host ""
Write-Host "Comandos útiles:"
Write-Host "  Restart-Service $Nombre        # tras actualizar el código"
Write-Host "  Get-Service $Nombre"
Write-Host "  Get-Content '$Registros\metaflotpy.err.log' -Tail 50 -Wait"
