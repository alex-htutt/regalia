#Requires -Version 5.1
<#
.SYNOPSIS
    Regalia installer / bootstrap for Windows.

.DESCRIPTION
    Regalia ships as a self-contained Regalia.exe (all Python deps are baked in),
    so there is nothing to pip-install. This helper handles the two things the exe
    can NOT do for itself:

      1. The Edge WebView2 runtime - the desktop window's backend. The app *is* a
         WebView2 window, so it can't install WebView2 from inside itself; this
         script does it first (it's already present on Windows 11 / modern Win 10).
      2. Optional AI backends you choose from a checklist - Ollama + a local model
         (free/offline Fast tier), the Claude Code CLI, and the OpenAI Codex CLI.

    It installs Regalia into a PER-USER folder (%LOCALAPPDATA%\Regalia) on purpose:
    that keeps the built-in self-update (which replaces the running exe in place)
    working. It never writes to Program Files and never needs admin for Regalia
    itself (individual backend installers may prompt for elevation of their own).

.PARAMETER All
    Non-interactive: do every optional step (WebView2, Ollama+model, Claude CLI,
    Codex CLI, shortcut). Good for scripted setups.

.PARAMETER WebView2
    Non-interactive: install the WebView2 runtime. Passing any explicit switch (or
    -All) skips the interactive checklist. WebView2 is always installed if missing.

.PARAMETER Ollama
    Non-interactive: install Ollama and pull -Model.

.PARAMETER ClaudeCli
    Non-interactive: install the Claude Code CLI (needs Node/npm).

.PARAMETER CodexCli
    Non-interactive: install the OpenAI Codex CLI (needs Node/npm).

.PARAMETER Shortcut
    Non-interactive: create a Start Menu shortcut.

.PARAMETER Model
    Ollama model to pull when Ollama is selected (default: llama3.2).

.PARAMETER InstallDir
    Where Regalia.exe is installed (default: %LOCALAPPDATA%\Regalia).

.PARAMETER NoLaunch
    Don't launch Regalia when finished.

.EXAMPLE
    .\install.ps1                 # interactive checklist
.EXAMPLE
    .\install.ps1 -All            # install everything, no prompts
.EXAMPLE
    .\install.ps1 -Ollama -Model qwen2.5:7b -NoLaunch
#>
[CmdletBinding()]
param(
    [switch]$All,
    [switch]$WebView2,
    [switch]$Ollama,
    [switch]$ClaudeCli,
    [switch]$CodexCli,
    [switch]$Shortcut,
    [switch]$NoLaunch,
    [string]$Model = "llama3.2",
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Regalia")
)

$ErrorActionPreference = "Stop"
# Older Windows defaults to TLS 1.0 for .NET web calls, which GitHub/Microsoft
# reject - force TLS 1.2 so the downloads below don't fail on a fresh machine.
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocol]::Tls12 } catch {}

$RepoExeUrl = "https://github.com/alex-htutt/regalia/releases/latest/download/Regalia.exe"
$WebView2Url = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"  # Evergreen bootstrapper

# --- tiny console helpers ----------------------------------------------------
function Write-Head($t) { Write-Host ""; Write-Host "  $t" -ForegroundColor Cyan }
function Write-Info($t) { Write-Host "  - $t" -ForegroundColor Gray }
function Write-Ok($t)   { Write-Host "  [ok] $t" -ForegroundColor Green }
function Write-Warn($t) { Write-Host "  [!] $t" -ForegroundColor Yellow }
function Write-Err($t)  { Write-Host "  [x] $t" -ForegroundColor Red }

function Confirm-Step($question, $default = $true) {
    $hint = if ($default) { "[Y/n]" } else { "[y/N]" }
    $ans = Read-Host "  $question $hint"
    if ([string]::IsNullOrWhiteSpace($ans)) { return $default }
    return ($ans -match '^(y|yes)$')
}

# --- detection ---------------------------------------------------------------
function Test-WebView2 {
    # Present when the Evergreen runtime's EdgeUpdate client reports a real version.
    $guid = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
    $keys = @(
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\$guid",
        "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$guid",
        "HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$guid"
    )
    foreach ($k in $keys) {
        try {
            $pv = (Get-ItemProperty -Path $k -Name pv -ErrorAction Stop).pv
            if ($pv -and $pv -ne '0.0.0.0') { return $true }
        } catch {}
    }
    return $false
}

function Test-Ollama {
    if (Get-Command ollama -ErrorAction SilentlyContinue) { return $true }
    return (Test-Path (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"))
}

function Get-OllamaExe {
    $cmd = Get-Command ollama -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $p = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path $p) { return $p }
    return $null
}

function Test-Npm { return [bool](Get-Command npm -ErrorAction SilentlyContinue) }

# --- installers --------------------------------------------------------------
function Install-WebView2 {
    Write-Info "Downloading the Edge WebView2 runtime bootstrapper..."
    $out = Join-Path $env:TEMP "MicrosoftEdgeWebview2Setup.exe"
    Invoke-WebRequest -Uri $WebView2Url -OutFile $out -UseBasicParsing
    Write-Info "Installing WebView2 (silent)..."
    $p = Start-Process -FilePath $out -ArgumentList "/silent", "/install" -Wait -PassThru
    if ($p.ExitCode -eq 0) { Write-Ok "WebView2 runtime installed." }
    else { Write-Warn "WebView2 installer exited with code $($p.ExitCode)." }
}

function Install-Ollama {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Info "Installing Ollama via winget..."
        winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -eq 0) { Write-Ok "Ollama installed."; return }
        Write-Warn "winget install failed (exit $LASTEXITCODE); falling back to the official installer."
    }
    Write-Info "Downloading the Ollama installer..."
    $out = Join-Path $env:TEMP "OllamaSetup.exe"
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $out -UseBasicParsing
    Write-Info "Launching the Ollama installer - follow its prompts..."
    Start-Process -FilePath $out -Wait
}

function Invoke-OllamaPull($model) {
    $exe = Get-OllamaExe
    if (-not $exe) { Write-Warn "Ollama not found on PATH yet - open a new terminal and run: ollama pull $model"; return }
    Write-Info "Pulling model '$model' (this can take a while)..."
    & $exe pull $model
    if ($LASTEXITCODE -eq 0) { Write-Ok "Model '$model' ready." }
    else { Write-Warn "Model pull exited with code $LASTEXITCODE - you can retry from Settings in the app." }
}

function Install-NpmCli($pkg, $label) {
    if (-not (Test-Npm)) {
        Write-Warn "$label needs Node.js/npm, which wasn't found. Install Node from https://nodejs.org and re-run, or set it up later in Settings."
        return
    }
    Write-Info "Installing $label ($pkg) globally via npm..."
    npm install -g $pkg
    if ($LASTEXITCODE -eq 0) { Write-Ok "$label installed." }
    else { Write-Warn "$label install exited with code $LASTEXITCODE. You can also configure it later in Settings." }
}

function Get-Regalia($installDir) {
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
    $dest = Join-Path $installDir "Regalia.exe"
    # Prefer an exe already sitting next to this script (both downloaded from the
    # release page); otherwise pull the latest release binary from GitHub.
    $local = Join-Path $PSScriptRoot "Regalia.exe"
    if ((Test-Path $local) -and ((Resolve-Path $local).Path -ne $dest)) {
        Write-Info "Copying Regalia.exe from the download folder..."
        Copy-Item $local $dest -Force
    } else {
        Write-Info "Downloading the latest Regalia.exe..."
        Invoke-WebRequest -Uri $RepoExeUrl -OutFile $dest -UseBasicParsing
    }
    Write-Ok "Regalia installed at $dest"
    return $dest
}

function New-Shortcut($target, $installDir) {
    try {
        $ws = New-Object -ComObject WScript.Shell
        $lnkPath = Join-Path ([Environment]::GetFolderPath("Programs")) "Regalia.lnk"
        $lnk = $ws.CreateShortcut($lnkPath)
        $lnk.TargetPath = $target
        $lnk.WorkingDirectory = $installDir
        $lnk.Description = "Regalia"
        $lnk.Save()
        Write-Ok "Start Menu shortcut created."
    } catch {
        Write-Warn "Couldn't create the shortcut: $($_.Exception.Message)"
    }
}

# --- main --------------------------------------------------------------------
Write-Host ""
Write-Host "  Regalia installer" -ForegroundColor White
Write-Host "  =================" -ForegroundColor DarkGray

$hasWebView2 = Test-WebView2
$explicit = $All -or $WebView2 -or $Ollama -or $ClaudeCli -or $CodexCli -or $Shortcut

if ($explicit) {
    $doWebView2 = ($All -or $WebView2) -and -not $hasWebView2
    $doOllama   = $All -or $Ollama
    $doClaude   = $All -or $ClaudeCli
    $doCodex    = $All -or $CodexCli
    $doShortcut = $All -or $Shortcut
} else {
    Write-Head "Choose what to set up (press Enter for the default):"
    if ($hasWebView2) { Write-Ok "WebView2 runtime already present - nothing to install there." }
    else { Write-Warn "WebView2 runtime is missing - it will be installed (the app window needs it)." }
    $doWebView2 = $false  # forced below when missing
    $doOllama   = Confirm-Step "Install Ollama + a local model? (Fast tier - free, private, offline)" $true
    $doClaude   = Confirm-Step "Install the Claude Code CLI? (Claude subscription tier)" $false
    $doCodex    = Confirm-Step "Install the OpenAI Codex CLI? (ChatGPT tier)" $false
    $doShortcut = Confirm-Step "Create a Start Menu shortcut?" $true
}

# WebView2 is required for the desktop window - always install it if it's missing,
# whatever the switches say.
if (-not $hasWebView2) { $doWebView2 = $true }

Write-Head "Installing..."

# 1. Get Regalia itself in place first, so a later failure still leaves a usable app.
$exePath = $null
try { $exePath = Get-Regalia $InstallDir }
catch { Write-Err "Couldn't download Regalia.exe: $($_.Exception.Message)"; Write-Err "Aborting."; exit 1 }

# 2. Optional / required components - each isolated so one failure can't sink the rest.
if ($doWebView2) { try { Install-WebView2 } catch { Write-Warn "WebView2 step failed: $($_.Exception.Message)" } }

if ($doOllama) {
    try {
        if (Test-Ollama) { Write-Ok "Ollama already installed." } else { Install-Ollama }
        Invoke-OllamaPull $Model
    } catch { Write-Warn "Ollama step failed: $($_.Exception.Message)" }
}

if ($doClaude) { try { Install-NpmCli "@anthropic-ai/claude-code" "Claude Code CLI" } catch { Write-Warn "Claude CLI step failed: $($_.Exception.Message)" } }
if ($doCodex)  { try { Install-NpmCli "@openai/codex" "OpenAI Codex CLI" } catch { Write-Warn "Codex CLI step failed: $($_.Exception.Message)" } }

if ($doShortcut) { New-Shortcut $exePath $InstallDir }

# 3. Done - launch (unless told not to). The app's own first-run wizard picks up
# from here to finish configuring whichever backends you chose.
Write-Head "All set."
Write-Info "Regalia: $exePath"
Write-Info "Anything you skipped can be set up later in the app's Settings."

if (-not $NoLaunch) {
    Write-Info "Launching Regalia..."
    Start-Process -FilePath $exePath
}
Write-Host ""
