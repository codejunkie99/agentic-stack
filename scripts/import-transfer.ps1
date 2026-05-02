param(
    [Parameter(Mandatory = $true)]
    [string]$Target,

    [Parameter(Mandatory = $true)]
    [string]$Payload,

    [Parameter(Mandatory = $true)]
    [string]$Sha256
)

$ErrorActionPreference = 'Stop'

if ($env:AGENTIC_STACK_ROOT -and (Test-Path (Join-Path $env:AGENTIC_STACK_ROOT 'harness_manager'))) {
    $Root = $env:AGENTIC_STACK_ROOT
} elseif ((Test-Path '.\harness_manager') -and (Test-Path '.\adapters')) {
    $Root = (Get-Location).Path
} else {
    $Temp = Join-Path ([System.IO.Path]::GetTempPath()) ("agentic-stack-transfer-" + [System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $Temp | Out-Null
    $Archive = Join-Path $Temp 'agentic-stack.tar.gz'
    Invoke-WebRequest -Uri 'https://github.com/codejunkie99/agentic-stack/archive/refs/heads/master.tar.gz' -OutFile $Archive
    tar -xzf $Archive -C $Temp --strip-components 1
    $Root = $Temp
}

$env:AGENTIC_STACK_ROOT = $Root
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$Root;$($env:PYTHONPATH)"
} else {
    $env:PYTHONPATH = $Root
}

$python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) {
    Write-Error 'python3 or python is required to run agentic-stack transfer import.'
    exit 1
}

& $python.Source -m harness_manager.cli transfer import --target $Target --payload $Payload --sha256 $Sha256
exit $LASTEXITCODE
