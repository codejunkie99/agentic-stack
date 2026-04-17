# install.ps1 — Windows PowerShell installer (parallel to install.sh)
# Usage:  .\install.ps1 <adapter-name> [target-dir] [-Yes] [-Reconfigure] [-Force]
#   adapter-name: claude-code | cursor | windsurf | opencode | openclaw | hermes | standalone-python
#   target-dir:   where your project lives (default: current dir)
#   -Yes          accept all wizard defaults (safe for CI)
#   -Reconfigure  re-run the wizard on an existing project
#   -Force        overwrite even customized PREFERENCES.md

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Adapter,

    [Parameter(Position = 1)]
    [string]$TargetDir = (Get-Location).Path,

    [switch]$Yes,
    [switch]$Reconfigure,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

$ValidAdapters = @(
    'claude-code', 'cursor', 'windsurf',
    'opencode', 'openclaw', 'hermes',
    'standalone-python'
)
if ($Adapter -notin $ValidAdapters) {
    Write-Error "unknown adapter '$Adapter'. valid: $($ValidAdapters -join ' ')"
    exit 1
}

$Src = Join-Path $Here "adapters/$Adapter"
if (-not (Test-Path $Src -PathType Container)) {
    Write-Error "adapter '$Adapter' not found at $Src"
    exit 1
}

Write-Host "installing '$Adapter' into $TargetDir"

# Copy .agent/ brain only if the target does not already have one
$TargetAgent = Join-Path $TargetDir ".agent"
if (-not (Test-Path $TargetAgent -PathType Container)) {
    Copy-Item -Path (Join-Path $Here ".agent") -Destination $TargetAgent -Recurse
    Write-Host "  + .agent/ (portable brain)"
}

switch ($Adapter) {
    'claude-code' {
        Copy-Item (Join-Path $Src 'CLAUDE.md') (Join-Path $TargetDir 'CLAUDE.md') -Force
        $claudeDir = Join-Path $TargetDir '.claude'
        New-Item -ItemType Directory -Path $claudeDir -Force | Out-Null
        Copy-Item (Join-Path $Src 'settings.json') (Join-Path $claudeDir 'settings.json') -Force
    }
    'cursor' {
        $rulesDir = Join-Path $TargetDir '.cursor/rules'
        New-Item -ItemType Directory -Path $rulesDir -Force | Out-Null
        Copy-Item (Join-Path $Src '.cursor/rules/agentic-stack.mdc') (Join-Path $rulesDir 'agentic-stack.mdc') -Force
    }
    'windsurf' {
        Copy-Item (Join-Path $Src '.windsurfrules') (Join-Path $TargetDir '.windsurfrules') -Force
    }
    'opencode' {
        Copy-Item (Join-Path $Src 'AGENTS.md') (Join-Path $TargetDir 'AGENTS.md') -Force
        Copy-Item (Join-Path $Src 'opencode.json') (Join-Path $TargetDir 'opencode.json') -Force
    }
    'openclaw' {
        Copy-Item (Join-Path $Src 'config.md') (Join-Path $TargetDir '.openclaw-system.md') -Force
    }
    'hermes' {
        Copy-Item (Join-Path $Src 'AGENTS.md') (Join-Path $TargetDir 'AGENTS.md') -Force
    }
    'standalone-python' {
        Copy-Item (Join-Path $Src 'run.py') (Join-Path $TargetDir 'run.py') -Force
    }
}

Write-Host "done."

# ── Onboarding wizard ──────────────────────────────────────────────
$OnboardPy = Join-Path $Here 'onboard.py'
if (-not (Test-Path $OnboardPy -PathType Leaf)) {
    Write-Host "tip: customize $TargetDir\.agent\memory\personal\PREFERENCES.md with your conventions."
    exit 0
}

$python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Host "tip: python3/python not found on PATH — edit .agent\memory\personal\PREFERENCES.md manually."
    exit 0
}

$wizardArgs = @($OnboardPy, $TargetDir)
if ($Yes)         { $wizardArgs += '--yes' }
if ($Reconfigure) { $wizardArgs += '--reconfigure' }
if ($Force)       { $wizardArgs += '--force' }

& $python.Source @wizardArgs
exit $LASTEXITCODE
