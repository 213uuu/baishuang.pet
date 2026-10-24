param(
    [Parameter(Mandatory = $true)]
    [string]$InputRoot,
    [Parameter(Mandatory = $true)]
    [string]$OutputRoot,
    [ValidateRange(0.05, 1.0)]
    [double]$DarkenFactor = 0.32,
    [ValidateRange(1, 64)]
    [int]$MinimumSpill = 4
)

$ErrorActionPreference = "Stop"
$tool = Join-Path $PSScriptRoot "suppress_green_residue.py"
$python = if ($env:BAISHUANG_PYTHON) {
    $env:BAISHUANG_PYTHON
}
else {
    (Get-Command python.exe -ErrorAction Stop).Source
}

& $python $tool `
    $InputRoot `
    $OutputRoot `
    --darken-factor $DarkenFactor `
    --minimum-spill $MinimumSpill
if ($LASTEXITCODE -ne 0) {
    throw "green residue suppression failed with exit code $LASTEXITCODE"
}
