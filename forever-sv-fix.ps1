$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 "$ScriptDir\forever_sv_fix.py" @args
    exit $LASTEXITCODE
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python "$ScriptDir\forever_sv_fix.py" @args
    exit $LASTEXITCODE
}

Write-Error "Python 3.10+ was not found."
exit 2
