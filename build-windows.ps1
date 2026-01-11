<#  build-windows.ps1 — Garage (Windows) v4.4.5
    Script de build Windows (portable) pour un repo multi-OS.

    Usage (PowerShell, à la racine du repo) :
      .\build-windows.ps1
      .\build-windows.ps1 -Version 4.4.5
      .\build-windows.ps1 -AppsDir "$env:USERPROFILE\Apps"
      .\build-windows.ps1 -KeepBuildDirs

    Notes:
    - Ce script NE lance PAS garage.py (tu testes avant).
    - Il génère dist\Garage.exe puis un ZIP dans releases\
#>

[CmdletBinding()]
param(
  [string]$Version = "4.4.5",
  [switch]$KeepBuildDirs,
  [string]$AppsDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Info($msg) { Write-Host "ℹ️  $msg" }
function Ok($msg)   { Write-Host "✅ $msg" }
function Warn($msg) { Write-Host "⚠️  $msg" }
function Fail($msg) { Write-Host "❌ $msg"; exit 1 }

# --- 0) Contexte / chemins ---
$Root      = (Get-Location).Path
$GaragePy  = Join-Path $Root "garage.py"
$AssetsDir = Join-Path $Root "assets"
$DataDir   = Join-Path $Root "data"

$IconIco = Join-Path $AssetsDir "logo.ico"
$LogoPng = Join-Path $AssetsDir "logo.png"
$AideMd  = Join-Path $AssetsDir "AIDE.md"
$EmptyDb = Join-Path $DataDir   "garage_empty.db"

$VenvDir  = Join-Path $Root ".venv"
$VenvPy   = Join-Path $VenvDir "Scripts\python.exe"
$Activate = Join-Path $VenvDir "Scripts\Activate.ps1"

$DistExe  = Join-Path $Root "dist\Garage.exe"
$OutDir   = Join-Path $Root "releases"
$ZipName  = "Garage-v$Version-windows-portable.zip"
$ZipPath  = Join-Path $OutDir $ZipName
$HashPath = "$ZipPath.sha256"

Info "Build Windows — Garage v$Version"
Info "Repo: $Root"

# --- 1) Vérifs fichiers requis ---
Info "Vérification des fichiers requis…"
if (!(Test-Path $GaragePy))  { Fail "garage.py introuvable à la racine." }
if (!(Test-Path $AssetsDir)) { Fail "Dossier assets/ introuvable." }
if (!(Test-Path $DataDir))   { Fail "Dossier data/ introuvable." }

if (!(Test-Path $IconIco)) { Fail "Manquant: assets\logo.ico" }
if (!(Test-Path $LogoPng)) { Fail "Manquant: assets\logo.png" }
if (!(Test-Path $AideMd))  { Fail "Manquant: assets\AIDE.md" }
if (!(Test-Path $EmptyDb)) { Fail "Manquant: data\garage_empty.db" }
Ok "Structure OK."

# --- 2) Venv + deps build ---
if (!(Test-Path $VenvPy)) {
  Info "Création du venv .venv…"
  python -m venv $VenvDir
  if (!(Test-Path $VenvPy)) { Fail "Échec création venv (.venv\Scripts\python.exe introuvable)." }
  Ok "Venv créé."
} else {
  Info "Venv déjà présent."
}

Info "Activation du venv…"
. $Activate

Info "Installation / mise à jour des dépendances build…"
& $VenvPy -m pip install --upgrade pip | Out-Host
& $VenvPy -m pip install pillow matplotlib pyinstaller | Out-Host
Ok "Dépendances OK."

# --- 3) Nettoyage build/dist/spec ---
if (-not $KeepBuildDirs) {
  Info "Nettoyage build/dist/Garage.spec…"
  Remove-Item -Recurse -Force (Join-Path $Root "build") -ErrorAction SilentlyContinue
  Remove-Item -Recurse -Force (Join-Path $Root "dist")  -ErrorAction SilentlyContinue
  Remove-Item -Force (Join-Path $Root "Garage.spec")    -ErrorAction SilentlyContinue
  Ok "Nettoyage OK."
} else {
  Warn "KeepBuildDirs activé: on conserve build/dist/spec."
}

# --- 4) Build PyInstaller ---
Info "Build PyInstaller…"
& $VenvPy -m PyInstaller `
  --name Garage `
  --onefile `
  --windowed `
  --icon "$IconIco" `
  --add-data "assets;assets" `
  --add-data "data;data" `
  "$GaragePy" | Out-Host

if (!(Test-Path $DistExe)) { Fail "Build terminé mais dist\Garage.exe introuvable." }
Ok "EXE généré: $DistExe"

# --- 5) ZIP de release + SHA256 ---
if (!(Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

Remove-Item -Force $ZipPath  -ErrorAction SilentlyContinue
Remove-Item -Force $HashPath -ErrorAction SilentlyContinue

Info "Création ZIP: $ZipName"
Compress-Archive -Path $DistExe -DestinationPath $ZipPath -Force
if (!(Test-Path $ZipPath)) { Fail "ZIP non créé: $ZipPath" }
Ok "ZIP créé: $ZipPath"

Info "Calcul SHA256…"
$hash = (Get-FileHash -Algorithm SHA256 -Path $ZipPath).Hash.ToLower()
"$hash  $ZipName" | Set-Content -Encoding ASCII -Path $HashPath
Ok "SHA256 OK (fichier: $HashPath)"

# --- 6) Option: copie dans AppsDir (mise à jour “au même chemin” pour garder les raccourcis) ---
if ($AppsDir.Trim() -ne "") {
  if (!(Test-Path $AppsDir)) {
    Info "Création AppsDir: $AppsDir"
    New-Item -ItemType Directory -Path $AppsDir | Out-Null
  }
  $DestExe = Join-Path $AppsDir "Garage.exe"
  Copy-Item -Force $DistExe $DestExe
  Ok "EXE copié vers: $DestExe"
}

# --- 7) Résumé ---
Write-Host ""
Write-Host "==================== RÉSUMÉ ===================="
Write-Host "Version       : v$Version"
Write-Host "EXE           : $DistExe"
Write-Host "ZIP release   : $ZipPath"
Write-Host "SHA256 file   : $HashPath"
if ($AppsDir.Trim() -ne "") { Write-Host "AppsDir copy  : $AppsDir\Garage.exe" }
Write-Host "================================================"
Write-Host ""
Ok "Build Windows terminé."
