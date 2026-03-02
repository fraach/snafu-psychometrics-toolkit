# Uso: Esegui questo script in PowerShell da dentro la cartella del progetto
# Consigliato: apri PowerShell come utente normale (non serve admin)
# Se serve abilitare l'esecuzione temporanea degli script:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

param(
  [switch]$InstallVSCode = $false,
  [switch]$InstallVisualStudio = $false,
  [string]$SnafuGitUrl = ""
)

function Test-Command {
  param([string]$Name)
  try { Get-Command $Name -ErrorAction Stop | Out-Null; return $true } catch { return $false }
}

function Ensure-Python {
  Write-Host "[1/5] Verifica Python..." -ForegroundColor Cyan
  if (Test-Command py) { return "py" }
  if (Test-Command python) { return "python" }

  Write-Host "Python non trovato. Provo installazione con winget..." -ForegroundColor Yellow
  if (-not (Test-Command winget)) {
    Write-Error "winget non disponibile. Installa Python da https://www.python.org/downloads/ e riavvia PowerShell."
    exit 1
  }
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements

  $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')

  if (Test-Command py) { return "py" }
  if (Test-Command python) { return "python" }
  Write-Error "Impossibile trovare Python anche dopo l'installazione. Chiudi e riapri PowerShell, poi riesegui questo script."
  exit 1
}

function Ensure-Venv {
  param([string]$Python)
  Write-Host "[2/5] Creo ambiente virtuale (.venv)..." -ForegroundColor Cyan
  if (-not (Test-Path .venv)) {
    & $Python -m venv .venv
  }
  $activate = Join-Path .venv "Scripts/Activate.ps1"
  if (-not (Test-Path $activate)) {
    Write-Error "Activate.ps1 non trovato in .venv. Creazione venv fallita."
    exit 1
  }
  Write-Host "[3/5] Attivo .venv e aggiorno pip..." -ForegroundColor Cyan
  & $activate
  python -m pip install --upgrade pip setuptools wheel
}

function Ensure-Requirements {
  Write-Host "[4/5] Installo dipendenze principali..." -ForegroundColor Cyan
  # Pacchetti core necessari anche senza snafu
  pip install --upgrade pip setuptools wheel
  pip install numpy pandas networkx matplotlib

  Write-Host "Provo ad installare 'snafu' (opzionale, richiesto per l'analisi)..." -ForegroundColor Cyan
  if ($SnafuGitUrl -and $SnafuGitUrl.Trim() -ne "") {
    Write-Host "Installo snafu da sorgente: $SnafuGitUrl" -ForegroundColor Cyan
    pip install $SnafuGitUrl
  } else {
    pip install snafu
  }
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Installazione 'snafu' non riuscita. Alcune funzioni (functions\analyze_snafu.py) non saranno disponibili."
    Write-Host "Suggerimenti:" -ForegroundColor Yellow
    Write-Host " - Verifica la connessione Internet" -ForegroundColor Yellow
    Write-Host " - Riprova: pip install snafu" -ForegroundColor Yellow
    Write-Host " - Se non è su PyPI, installa dal repo ufficiale (es. pip install git+https://github.com/<org>/<repo>.git)" -ForegroundColor Yellow
  }
}

function Test-PythonModule {
  param([string]$Module)
  python - <<PY 2>$null
import importlib, sys
sys.exit(0 if importlib.util.find_spec("$Module") else 1)
PY
  return ($LASTEXITCODE -eq 0)
}

function Run-Project {
  Write-Host "[5/5] Eseguo analisi e grafici..." -ForegroundColor Cyan
  $hasSnafu = Test-PythonModule -Module snafu
  if ($hasSnafu) {
    python functions\analyze_snafu.py
  } else {
    Write-Warning "Modulo 'snafu' non disponibile: salto functions\analyze_snafu.py."
    Write-Host "Se hai già file CSV in 'results/', posso generare comunque i grafici." -ForegroundColor Yellow
  }
  if (Test-Path (Join-Path "results" "psychometrics.csv") -and Test-Path (Join-Path "results" "network_metrics.csv")) {
    python functions\plot_snafu_results.py
    Write-Host "Output salvati in 'results' (csv e figure)." -ForegroundColor Green
  } else {
    Write-Warning "Grafici non generati: mancano i file CSV in 'results/'. Installa 'snafu' e riesegui lo script."
  }
}

function Optional-Editors {
  if ($InstallVSCode) {
    if (Test-Command winget) {
      Write-Host "Installo Visual Studio Code..." -ForegroundColor Cyan
      winget install -e --id Microsoft.VisualStudioCode --accept-package-agreements --accept-source-agreements
    } else {
      Write-Host "winget non disponibile. Scarica VS Code: https://code.visualstudio.com/" -ForegroundColor Yellow
    }
  }
  if ($InstallVisualStudio) {
    if (Test-Command winget) {
      Write-Host "Installo Visual Studio 2022 Community (installazione pesante, opzionale)..." -ForegroundColor Cyan
      winget install -e --id Microsoft.VisualStudio.2022.Community --accept-package-agreements --accept-source-agreements
      Write-Host "Per lo sviluppo Python in Visual Studio, aggiungi il workload 'Python development' dal Visual Studio Installer." -ForegroundColor Yellow
    } else {
      Write-Host "winget non disponibile. Scarica Visual Studio: https://visualstudio.microsoft.com/" -ForegroundColor Yellow
    }
  }
}

$pythonCmd = Ensure-Python
Ensure-Venv -Python $pythonCmd
Ensure-Requirements
Run-Project
Optional-Editors

Write-Host "Fatto. Per riutilizzare l'ambiente in futuro:" -ForegroundColor Green
Write-Host "  1) Apri PowerShell nella cartella del progetto" -ForegroundColor Gray
Write-Host "  2) Attiva: .\\.venv\\Scripts\\Activate.ps1" -ForegroundColor Gray
Write-Host "  3) Esegui: python functions\analyze_snafu.py (e poi functions\plot_snafu_results.py)" -ForegroundColor Gray
