<#
    Arranca MetaFlotPy con waitress en modo producción.

    Uso desde la raíz del proyecto:
        .\despliegue\windows\servir.ps1
        .\despliegue\windows\servir.ps1 -Puerto 8080 -Hilos 8

    Sirve para probar el servidor de producción a mano. Para dejarlo
    funcionando de forma permanente usa instalar-servicio.ps1.
#>
[CmdletBinding()]
param(
    [string]$Escucha = '127.0.0.1',
    [int]$Puerto = 8000,
    [int]$Hilos = 6,
    [string]$Venv = ''
)

$ErrorActionPreference = 'Stop'

# Raíz del proyecto = dos niveles por encima de este script
$Raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Raiz

if (-not $Venv) {
    # El entorno virtual suele estar junto al proyecto o un nivel más arriba
    foreach ($ruta in @("$Raiz\.venv", "$Raiz\venv", (Split-Path -Parent $Raiz))) {
        if (Test-Path "$ruta\Scripts\waitress-serve.exe") { $Venv = $ruta; break }
    }
}
if (-not $Venv) { throw "No se encontró el entorno virtual. Indícalo con -Venv <ruta>." }

$Waitress = Join-Path $Venv 'Scripts\waitress-serve.exe'
if (-not (Test-Path $Waitress)) {
    throw "Falta waitress en $Venv. Instálalo con:  $Venv\Scripts\pip.exe install -r requirements.txt"
}

# --- Variables de entorno ---
$env:METAFLOTPY_ENTORNO = 'produccion'

$archivoEnv = Join-Path $Raiz '.env'
if (Test-Path $archivoEnv) {
    Get-Content $archivoEnv | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2].Trim()
        }
    }
    Write-Host "Variables cargadas desde .env" -ForegroundColor DarkGray
}

if (-not $env:METAFLOTPY_SECRET_KEY) {
    throw @"
Falta METAFLOTPY_SECRET_KEY.
Genera una clave y guárdala en el archivo .env de la raíz del proyecto:

    $Venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
"@
}

# Detrás de Nginx o IIS hay que confiar en las cabeceras X-Forwarded-*
if (-not $env:METAFLOTPY_TRAS_PROXY) { $env:METAFLOTPY_TRAS_PROXY = '1' }

Write-Host ""
Write-Host "MetaFlotPy · waitress" -ForegroundColor Cyan
Write-Host "  proyecto : $Raiz"
Write-Host "  entorno  : $($env:METAFLOTPY_ENTORNO)"
Write-Host "  escucha  : http://$Escucha`:$Puerto"
Write-Host "  hilos    : $Hilos"
Write-Host ""

& $Waitress --listen="$Escucha`:$Puerto" --threads=$Hilos --channel-timeout=90 wsgi:app
