#Requires -Version 5.1

<#
.SYNOPSIS
    The Makefile's targets, for shells where make is not on the path.

.DESCRIPTION
    Each target runs the same tools on the same arguments the Makefile does, so a
    contributor on Windows proves the same things CI does. The Makefile is the original
    and this file is the copy: where the two disagree about what is checked, this one is
    wrong.

    Every tool is invoked as `python -m name` rather than through the executable pip
    generates in Scripts\. Those shims are unsigned binaries written at install time, and
    a managed Windows machine running Application Control refuses to start them: the same
    policy that makes invoice-extractor.exe fail is the one that lets
    "python -m invoice_extractor" run. It is also the more precise form, because it uses
    the module in the active environment rather than whatever the PATH resolves a bare
    name to.

    Kept to ASCII on purpose. Windows PowerShell 5.1 reads a script without a byte order
    mark in the system codepage, so a non-ASCII character here would arrive mangled on
    the machines this file exists for.

.PARAMETER Target
    One of install, corpus, demo, bench, lint, typecheck, test, check. Defaults to check.

.EXAMPLE
    .\make.ps1 check

.EXAMPLE
    .\make.ps1 demo
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('install', 'corpus', 'demo', 'bench', 'lint', 'typecheck', 'test', 'check')]
    [string] $Target = 'check'
)

$ErrorActionPreference = 'Stop'

# The version the packaging declares (requires-python in pyproject.toml). pip refuses
# the project outright below it. Failing here with one sentence beats failing later
# with a traceback.
$MinimumPython = [version] '3.10'

$DemoDocument = 'tests/forge/fixtures/corpus/0001_fr-FR_classic_s7.pdf'

function Assert-Python {
    <# The interpreter on the path is new enough to install and run this project. #>
    $reported = & python -c 'import sys; print(".".join(str(n) for n in sys.version_info[:3]))'
    if ($LASTEXITCODE -ne 0 -or -not $reported) {
        throw 'no python on the PATH - activate the virtual environment first'
    }
    if ([version] $reported -lt $MinimumPython) {
        throw "this project needs Python $MinimumPython or newer; the one on the PATH is $reported"
    }
}

function Invoke-Step {
    <# One command, announced before it runs and checked after it does. #>
    param(
        [Parameter(Mandatory = $true)] [string] $Name,
        [Parameter(Mandatory = $true)] [scriptblock] $Command
    )
    Write-Host ''
    Write-Host "==> $Name" -ForegroundColor Cyan
    $global:LASTEXITCODE = 0
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Invoke-Target {
    param([Parameter(Mandatory = $true)] [string] $Name)

    switch ($Name) {
        'install' {
            Invoke-Step 'install (both distributions, editable)' {
                python -m pip install -e '.[dev]' -e ./tools/forge
            }
            Invoke-Step 'install (pre-commit hooks)' { python -m pre_commit install }
        }
        'corpus' {
            Invoke-Step 'corpus' {
                python -m invoice_forge generate --plan corpus/plan.json --out corpus/
            }
        }
        'demo' {
            Invoke-Step 'demo' { python -m invoice_extractor extract $DemoDocument --report }
        }
        'bench' {
            Invoke-Step 'bench' { python -m benchmarks.run }
        }
        'lint' {
            Invoke-Step 'lint (ruff check)' { python -m ruff check . }
            Invoke-Step 'lint (ruff format)' { python -m ruff format --check . }
        }
        'typecheck' {
            Invoke-Step 'typecheck' { python -m mypy }
        }
        'test' {
            Invoke-Step 'test' { python -m pytest }
        }
        'check' {
            Invoke-Target 'lint'
            Invoke-Target 'typecheck'
            Invoke-Target 'test'
        }
    }
}

Push-Location $PSScriptRoot
try {
    Assert-Python
    Invoke-Target $Target
    Write-Host ''
    # ${Target}, not $Target: a colon straight after a variable name is how PowerShell
    # writes a scope or drive qualifier ($env:PATH), so the braces are what keep this a
    # variable followed by punctuation rather than a parse error.
    Write-Host "${Target}: OK" -ForegroundColor Green
}
catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
