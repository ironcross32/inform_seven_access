<#
.SYNOPSIS
    Cut an Inform Seven Access release: bump addon_version, commit, tag, and push.
.DESCRIPTION
    Run git release interactively from anywhere inside the repository. Enter
    accepts the next patch version; a leading v is also accepted. Only buildVars.py
    is committed. Commit changelog and other release changes before running this.
    The tag push triggers the existing GitHub Actions build/release workflow.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Fail($message) {
    Write-Host "release: $message" -ForegroundColor Red
    exit 1
}

if ([Console]::IsInputRedirected) {
    Fail 'this must be run interactively -- it prompts for the version.'
}

$repo = (& git rev-parse --show-toplevel)
if ($LASTEXITCODE -ne 0 -or -not $repo) { Fail 'not inside a git repository.' }
$repo = $repo.Trim()
$scriptRepo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if ([System.IO.Path]::GetFullPath($repo) -ne $scriptRepo) {
    Fail 'run this script from its own git repository.'
}

Push-Location -LiteralPath $repo
try {
    $versionPath = Join-Path $repo 'buildVars.py'
    if (-not (Test-Path -LiteralPath $versionPath)) { Fail 'buildVars.py was not found.' }
    $pattern = '(?m)^(\s*addon_version\s*=\s*")([^"\r\n]+)(")'
    $content = [System.IO.File]::ReadAllText($versionPath)
    $versionMatches = [regex]::Matches($content, $pattern)
    if ($versionMatches.Count -ne 1) { Fail 'expected exactly one addon_version in buildVars.py.' }
    $current = $versionMatches[0].Groups[2].Value

    # Drop a prerelease suffix and increment the last numeric component.
    $parts = (($current -split '[-+]')[0]) -split '\.'
    $default = $null
    if ($parts[-1] -match '^\d+$') {
        $parts[-1] = ([long]$parts[-1] + 1).ToString()
        $default = $parts -join '.'
    }

    Write-Host ""
    Write-Host "Current addon_version: $current"
    if ($default) {
        $answer = Read-Host "Version to release [$default]"
    } else {
        $answer = Read-Host 'Version to release'
    }
    if ([string]::IsNullOrWhiteSpace($answer)) { $answer = $default }
    if ([string]::IsNullOrWhiteSpace($answer)) { Fail 'no version given.' }
    $version = $answer.Trim() -replace '^[vV]', ''
    if ($version -notmatch '^\d+(\.\d+)*(-[0-9A-Za-z.-]+)?$') {
        Fail "'$version' does not look like a version number."
    }
    $tag = "v$version"
    if ($version -eq $current) { Fail "addon_version is already $current. Pick a new version." }

    $branch = (& git symbolic-ref --quiet --short HEAD)
    if ($LASTEXITCODE -ne 0 -or -not $branch) { Fail 'HEAD is detached; check out a branch first.' }
    & git ls-files --error-unmatch -- buildVars.py | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail 'buildVars.py must already be tracked.' }
    $changes = (& git status --porcelain -- buildVars.py)
    if ($LASTEXITCODE -ne 0) { Fail 'could not check buildVars.py for changes.' }
    if ($changes) { Fail 'commit or stash existing buildVars.py changes before releasing.' }

    $existing = (& git tag --list $tag)
    if ($LASTEXITCODE -ne 0) { Fail 'could not check local tags.' }
    if ($existing) { Fail "tag $tag already exists locally. Nothing has been changed." }
    $remote = (& git ls-remote --tags origin "refs/tags/$tag")
    if ($LASTEXITCODE -ne 0) { Fail 'could not check tags on origin. Nothing has been changed.' }
    if ($remote) { Fail "tag $tag already exists on origin. Nothing has been changed." }

    Write-Host ""
    Write-Host "Releasing $tag (addon_version $current -> $version) from branch $branch"
    $value = $versionMatches[0].Groups[2]
    $updated = $content.Remove($value.Index, $value.Length).Insert($value.Index, $version)
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($versionPath, $updated, $utf8NoBom)

    # An explicit path keeps unrelated staged changes out of the release commit.
    & git commit --only -m "Release $tag" -- buildVars.py
    if ($LASTEXITCODE -ne 0) {
        Fail 'git commit failed. buildVars.py has been edited but nothing was tagged.'
    }
    & git tag -a $tag -m "Release $tag"
    if ($LASTEXITCODE -ne 0) { Fail "git tag failed. The bump is committed; create $tag by hand." }

    # Push the branch first so the release commit also belongs to the remote branch.
    & git push origin "HEAD:refs/heads/$branch"
    if ($LASTEXITCODE -ne 0) {
        Fail "pushing $branch failed. $tag exists locally; push the branch, then git push origin refs/tags/$tag."
    }
    & git push origin "refs/tags/$tag"
    if ($LASTEXITCODE -ne 0) { Fail "pushing $tag failed. Run: git push origin refs/tags/$tag" }

    Write-Host ""
    Write-Host "Pushed $tag. Check GitHub Actions for the add-on build and release." -ForegroundColor Green
} finally {
    Pop-Location
}
