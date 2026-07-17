<#
    Apply the Founder's Edition workflow into the vault root.
    Copies .cursor/rules/*, the area CLAUDE.md files, and the course-setup skill
    into place. Existing files are skipped unless -Force is passed.

    Usage:  ./founders-edition/apply.ps1 [-Force]
#>
param([switch]$Force)

$ErrorActionPreference = "Stop"
$bundle = $PSScriptRoot
$root   = Split-Path $bundle -Parent

$copied = 0; $skipped = 0
Get-ChildItem -Path $bundle -Recurse -File |
    Where-Object { $_.Name -notin @("README.md", "apply.ps1", "apply.sh") } |
    ForEach-Object {
        $rel  = $_.FullName.Substring($bundle.Length).TrimStart('\', '/')
        $dest = Join-Path $root $rel
        if ((Test-Path $dest) -and -not $Force) {
            Write-Host "skip  $rel (exists; -Force to overwrite)"
            $skipped++
        } else {
            New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
            Copy-Item $_.FullName -Destination $dest -Force
            Write-Host "copy  $rel"
            $copied++
        }
    }
Write-Host "`nDone: $copied copied, $skipped skipped. Reload Cursor / Claude Code to pick up the rules and skill."
