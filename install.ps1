# install.ps1 — Windows PowerShell installer (parallel to install.sh)
# Usage:  .\install.ps1 <adapter-name> [target-dir] [-Yes] [-Reconfigure] [-Force]
#   adapter-name: claude-code | cursor | windsurf | opencode | openclaw | hermes | codex | standalone-python | antigravity
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
    'opencode', 'openclaw', 'hermes', 'codex',
    'standalone-python', 'antigravity'
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
    'codex' {
        # Mirror install.sh: openclaw-style merge-or-alert on existing AGENTS.md.
        $agentsMd = Join-Path $TargetDir 'AGENTS.md'
        if (Test-Path $agentsMd -PathType Leaf) {
            $existing = Get-Content -Path $agentsMd -Raw -ErrorAction SilentlyContinue
            if ($existing -match '\.agent/') {
                Write-Host "  ~ AGENTS.md already references .agent/ — leaving alone"
            } else {
                Write-Host "  ! AGENTS.md exists but does not reference .agent/; not overwriting."
                Write-Host "    merge this block into your AGENTS.md to wire the brain:"
                Write-Host "    ---8<---"
                Get-Content -Path (Join-Path $Src 'AGENTS.md') | ForEach-Object { Write-Host "    $_" }
                Write-Host "    --->8---"
            }
        } else {
            Copy-Item (Join-Path $Src 'AGENTS.md') $agentsMd -Force
            Write-Host "  + AGENTS.md"
        }

        # Codex scans .agents/skills/ — keep the portable brain authoritative.
        $agentsDir = Join-Path $TargetDir '.agents'
        New-Item -ItemType Directory -Path $agentsDir -Force | Out-Null
        $skillsSrc = Join-Path $TargetAgent 'skills'
        $skillsDst = Join-Path $agentsDir 'skills'

        # Detect symlink/junction BEFORE Remove-Item: on PowerShell 5.1
        # `Remove-Item -Recurse` on a symlink can delete the target's
        # contents. Use IsLink detection + .NET Delete (or repoint).
        $skillsDstItem = Get-Item -LiteralPath $skillsDst -Force -ErrorAction SilentlyContinue
        $isLink = $false
        if ($skillsDstItem) {
            $isLink = ($skillsDstItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq [System.IO.FileAttributes]::ReparsePoint
        }

        if ($skillsDstItem -and $isLink) {
            # Existing link: delete the link only (NOT its target), then re-create.
            try {
                [System.IO.Directory]::Delete($skillsDst, $false)
            } catch {
                # Some Windows configurations require File.Delete for file-style links.
                [System.IO.File]::Delete($skillsDst)
            }
            try {
                New-Item -ItemType SymbolicLink -Path $skillsDst -Target $skillsSrc -ErrorAction Stop | Out-Null
                Write-Host "  + .agents/skills -> $skillsSrc (relinked)"
            } catch {
                Copy-Item -Path $skillsSrc -Destination $skillsDst -Recurse
                Write-Host "  + .agents/skills (copy; symlink not supported here)"
            }
        } elseif ($skillsDstItem) {
            # Real directory: sync with delete-orphans by replacing it whole.
            # Removing a real directory with -Recurse is safe; only links are dangerous.
            Remove-Item -LiteralPath $skillsDst -Recurse -Force
            try {
                New-Item -ItemType SymbolicLink -Path $skillsDst -Target $skillsSrc -ErrorAction Stop | Out-Null
                Write-Host "  + .agents/skills -> $skillsSrc (replaced stale copy)"
            } catch {
                Copy-Item -Path $skillsSrc -Destination $skillsDst -Recurse
                Write-Host "  ~ replaced .agents/skills with current .agent/skills (no symlink)"
            }
        } else {
            try {
                New-Item -ItemType SymbolicLink -Path $skillsDst -Target $skillsSrc -ErrorAction Stop | Out-Null
                Write-Host "  + .agents/skills -> $skillsSrc"
            } catch {
                Copy-Item -Path $skillsSrc -Destination $skillsDst -Recurse
                Write-Host "  + .agents/skills (copy; symlink not supported here)"
            }
        }
    }
    'standalone-python' {
        Copy-Item (Join-Path $Src 'run.py') (Join-Path $TargetDir 'run.py') -Force
    }
    'antigravity' {
        Copy-Item (Join-Path $Src 'ANTIGRAVITY.md') (Join-Path $TargetDir 'ANTIGRAVITY.md') -Force
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
