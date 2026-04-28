# install.ps1 — agentic-stack installer (Windows PowerShell parallel to install.sh)
#
# Usage:
#   .\install.ps1 <adapter-name> [target-dir] [-Yes] [-Reconfigure] [-Force]
#                                              # install one adapter
#   .\install.ps1 add <adapter-name> [target-dir]
#                                              # add an adapter to an
#                                              # already-set-up project
#   .\install.ps1 remove <adapter-name> [target-dir] [-Yes]
#                                              # remove an installed adapter
#   .\install.ps1 doctor [target-dir]          # read-only audit
#   .\install.ps1 status [target-dir]          # one-screen view
#   .\install.ps1                              # bare: list adapters / what
#                                              # to add
#
# adapter-name: claude-code | cursor | windsurf | opencode | openclaw |
# hermes | pi | codex | standalone-python | antigravity | gemini-cli
#
# All real logic lives in harness_manager/ (Python). This script is a
# thin dispatcher so install.sh and install.ps1 share one backend —
# manifest semantics, file substitution, openclaw_register_workspace,
# install.json — all behave identically across platforms.

[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args,

    [switch]$Yes,
    [switch]$Reconfigure,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:AGENTIC_STACK_ROOT = $Here

# Prepend Here to PYTHONPATH so `python -m harness_manager.cli` resolves
# the module regardless of which directory the user invoked from.
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$Here;$($env:PYTHONPATH)"
} else {
    $env:PYTHONPATH = $Here
}

# Resolve a python interpreter. Stock Windows ships `python` (not `python3`);
# Windows-with-WSL or Windows-with-py-launcher might have either. Try in order.
$python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Error "python3 or python is required but was not found on PATH. agentic-stack uses python for the installer + brain tooling."
    exit 1
}

# Build the argv to pass to harness_manager.cli. Preserve the flags that
# install.sh accepts: --yes, --reconfigure, --force.
$cliArgs = @()
if ($Args) { $cliArgs += $Args }
if ($Yes)         { $cliArgs += '--yes' }
if ($Reconfigure) { $cliArgs += '--reconfigure' }
if ($Force)       { $cliArgs += '--force' }

# Hand off. -m runs the module; the dispatcher owns argv parsing.
& $python.Source -m harness_manager.cli @cliArgs
exit $LASTEXITCODE
