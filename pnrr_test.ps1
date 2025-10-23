# Esecuzione pipeline PNRR: keep_columns -> filter -> analyze -> plot
param(
  [string]$Raw = "fluency_data\Snafu_2025-10-22_10-02-58.csv",
  [string]$Patients = "",
  [string[]]$StudyId = @(),
  [string]$IdPrefix = "",
  [string]$IdSuffix = "",
  [string]$SepData = $null,
  [string]$SepPat = $null,
  [int]$MinOTRun = 3,
  [string[]]$Categories = @(),
  [switch]$ForceMerge
)

function Run-Cmd {
  param([string[]]$Args)
  Write-Host "`n> $($Args -join ' ')" -ForegroundColor Cyan
  & $Args[0] $Args[1..($Args.Length-1)]
  if ($LASTEXITCODE -ne 0) { throw "Comando fallito: $($Args -join ' ')" }
}

$combined = "fluency_data\snafu_pnrr.csv"
$maleOut  = "fluency_data\snafu_pnrr_male.csv"
$femOut   = "fluency_data\snafu_pnrr_female.csv"

# 1) keep_columns
$kc = @("python","keep_columns.py", $Raw, "-o", $combined)
if ($SepData) { $kc += @("--sep", $SepData) }
if ($IdPrefix) { $kc += @("--id-prefix", $IdPrefix) }
if ($IdSuffix) { $kc += @("--id-suffix", $IdSuffix) }
if ($Patients -and $StudyId.Count -gt 0) {
  $kc += @("--patient-csv", $Patients, "--study-id")
  $kc += $StudyId
  if ($SepPat) { $kc += @("--sep-pat", $SepPat) }
  $kc += @("--output-male", $maleOut, "--output-female", $femOut)
}
Run-Cmd $kc

# 2) filter (merge + OT)
Run-Cmd @("py","filter.py","--input",$combined,"--schemes","schemes","--output","fluency_data\filtered_snafu.csv","--min-ot-run",$MinOTRun)

# 3) analyze
$a = @("py","analyze_snafu.py","--filtered-file","fluency_data\filtered_snafu.csv","--scheme-dir","schemes","--results-dir","results")
if ($Categories.Count -gt 0) { $a += @("--categories"); $a += $Categories }
if ($ForceMerge) { $a += @("--force-merge") }
Run-Cmd $a

# 4) plot
Run-Cmd @("py","plot_snafu_results.py")

Write-Host "\nCompletato. Vedi la cartella 'results' per CSV e grafici." -ForegroundColor Green

