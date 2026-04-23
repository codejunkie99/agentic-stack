# install.ps1 — Windows PowerShell installer (parallel to install.sh)
# Usage:  .\install.ps1 <adapter-name> [target-dir] [-Yes] [-Reconfigure] [-Force]
#   adapter-name: claude-code | cursor | windsurf | opencode | openclaw | hermes | pi | codex | standalone-python | antigravity
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
    'opencode', 'openclaw', 'hermes', 'pi', 'codex',
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
        # 1. Backward-compat: drop the system-prompt include
        Copy-Item (Join-Path $Src 'config.md') (Join-Path $TargetDir '.openclaw-system.md') -Force
        Write-Host "  + .openclaw-system.md (system-prompt include; backward compat)"

        # 2. OpenClaw auto-injects AGENTS.md from the workspace root.
        #    Safely handle an existing AGENTS.md (codex/aider/cline also use it).
        $ocAgentsPath = Join-Path $TargetDir 'AGENTS.md'
        $ocTemplate = Join-Path $Src 'AGENTS.md'
        if (Test-Path $ocAgentsPath -PathType Leaf) {
            $ocExisting = Get-Content -Path $ocAgentsPath -Raw -ErrorAction SilentlyContinue
            if ($ocExisting -match '\.agent/') {
                Write-Host "  ~ AGENTS.md already references .agent/ — leaving alone"
            } else {
                Write-Host "  ! AGENTS.md exists but does not reference .agent/; not overwriting."
                Write-Host "    merge this block into your AGENTS.md to wire the brain:"
                Write-Host "    ---8<---"
                Get-Content -Path $ocTemplate | ForEach-Object { Write-Host "    $_" }
                Write-Host "    --->8---"
            }
        } else {
            Copy-Item $ocTemplate $ocAgentsPath -Force
            Write-Host "  + AGENTS.md (auto-injected by OpenClaw from the workspace root)"
        }

        # 3. Register a project-scoped OpenClaw agent so its workspace == this project.
        $ocAbs = (Resolve-Path $TargetDir).Path
        $ocBnRaw = Split-Path -Leaf $ocAbs
        # lowercase first (OpenClaw normalizes agent ids to lowercase), then sanitize
        $ocBnSafe = ($ocBnRaw.ToLower() -replace '[^a-z0-9._-]', '-') -replace '-+', '-'
        $ocBnSafe = $ocBnSafe.Trim('-')
        if ([string]::IsNullOrEmpty($ocBnSafe)) { $ocBnSafe = 'project' }
        # 6-hex-char SHA1 suffix of the absolute path for cross-project uniqueness
        $ocSha = [System.Security.Cryptography.SHA1]::Create()
        $ocBytes = [System.Text.Encoding]::UTF8.GetBytes($ocAbs)
        $ocHashHex = -join (($ocSha.ComputeHash($ocBytes)) | ForEach-Object { $_.ToString('x2') })
        $ocAgentName = "$ocBnSafe-$($ocHashHex.Substring(0,6))"

        $ocBin = Get-Command openclaw -ErrorAction SilentlyContinue
        if ($ocBin) {
            Write-Host "  → registering OpenClaw agent '$ocAgentName' (workspace: $ocAbs)"
            try {
                $ocOut = & openclaw agents add $ocAgentName --workspace $ocAbs 2>&1
                $ocRc = $LASTEXITCODE
                $ocOut | ForEach-Object { Write-Host "    $_" }
                $ocOutJoined = ($ocOut | Out-String)
                if ($ocRc -eq 0) {
                    Write-Host "  ✓ registered. run from anywhere: openclaw --agent $ocAgentName"
                } elseif ($ocOutJoined -match '(?i)already exists') {
                    Write-Host "  ✓ already registered (idempotent re-run). run: openclaw --agent $ocAgentName"
                } else {
                    Write-Host "  ! 'openclaw agents add' failed (details above)."
                    Write-Host "    if your OpenClaw fork does not support 'agents add --workspace',"
                    Write-Host "    fall back to the system-prompt include we wrote:"
                    Write-Host "      openclaw --system-prompt-file `"$ocAbs\.openclaw-system.md`""
                    Write-Host "    otherwise retry: openclaw agents add `"$ocAgentName`" --workspace `"$ocAbs`""
                }
            } catch {
                Write-Host "  ! 'openclaw agents add' errored: $_"
                Write-Host "    fall back to the system-prompt include:"
                Write-Host "      openclaw --system-prompt-file `"$ocAbs\.openclaw-system.md`""
                Write-Host "    or retry: openclaw agents add `"$ocAgentName`" --workspace `"$ocAbs`""
            }
        } else {
            Write-Host "  ! 'openclaw' CLI not found on PATH. after installing OpenClaw, try:"
            Write-Host "      openclaw agents add `"$ocAgentName`" --workspace `"$ocAbs`""
            Write-Host "      openclaw --agent $ocAgentName"
            Write-Host "    or, on forks without 'agents add', use the system-prompt include:"
            Write-Host "      openclaw --system-prompt-file `"$ocAbs\.openclaw-system.md`""
        }
    }
    'hermes' {
        Copy-Item (Join-Path $Src 'AGENTS.md') (Join-Path $TargetDir 'AGENTS.md') -Force
    }
    'pi' {
        $agentsMd = Join-Path $TargetDir 'AGENTS.md'
        if (Test-Path $agentsMd -PathType Leaf) {
            Write-Host "  ~ $agentsMd already exists — skipping (pi reads whatever is there)"
        } else {
            Copy-Item (Join-Path $Src 'AGENTS.md') $agentsMd -Force
            Write-Host "  + AGENTS.md"
        }

        $piDir = Join-Path $TargetDir '.pi'
        New-Item -ItemType Directory -Path $piDir -Force | Out-Null

        $skillsSrc = Join-Path $TargetAgent 'skills'
        $skillsDst = Join-Path $piDir 'skills'

        # CRITICAL: detect symlink BEFORE Remove-Item. On PowerShell 5.1
        # (Windows default), `Remove-Item -Recurse -Force` on a symlink
        # traverses INTO the target and deletes its contents. Re-running
        # the installer would silently wipe .agent/skills via the link.
        # Use IsLink detection + .NET Delete (link only, not target).
        $skillsDstItem = Get-Item -LiteralPath $skillsDst -Force -ErrorAction SilentlyContinue
        if ($skillsDstItem) {
            $isLink = ($skillsDstItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq [System.IO.FileAttributes]::ReparsePoint
            if ($isLink) {
                try { [System.IO.Directory]::Delete($skillsDst, $false) }
                catch { [System.IO.File]::Delete($skillsDst) }
            } else {
                Remove-Item -LiteralPath $skillsDst -Recurse -Force
            }
        }
        try {
            New-Item -ItemType SymbolicLink -Path $skillsDst -Target $skillsSrc -ErrorAction Stop | Out-Null
            Write-Host "  + .pi/skills -> $skillsSrc"
        } catch {
            Copy-Item -Path $skillsSrc -Destination $skillsDst -Recurse
            Write-Host "  + .pi/skills (copy; symlink not supported here)"
        }

        $extensionsDir = Join-Path $piDir 'extensions'
        New-Item -ItemType Directory -Path $extensionsDir -Force | Out-Null
        Copy-Item (Join-Path $Src 'memory-hook.ts') (Join-Path $extensionsDir 'memory-hook.ts') -Force
        Write-Host "  + .pi/extensions/memory-hook.ts"
        # Upgrade path: the .agent copy higher up is skipped when .agent
        # already exists, but the pi extension calls this python hook,
        # so sync it explicitly.
        $hooksDir = Join-Path $TargetAgent 'harness/hooks'
        New-Item -ItemType Directory -Path $hooksDir -Force | Out-Null
        Copy-Item (Join-Path $Here '.agent/harness/hooks/pi_post_tool.py') (Join-Path $hooksDir 'pi_post_tool.py') -Force
        Write-Host "  + .agent/harness/hooks/pi_post_tool.py (synced for upgrades)"
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
