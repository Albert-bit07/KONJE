# Creates a private GitHub repository from the checked, whitelisted KONJE files.
# Requirements: git and authenticated GitHub CLI ('gh auth login').
# Run after unpacking the source into your intended KONJE working directory.
$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'CMakeLists.txt') -or -not (Test-Path 'src/main.cpp')) {
  throw 'Run this from your KONJE source root, not from an arbitrary Windows folder.'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Install Git for Windows first.' }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'Install GitHub CLI (gh) first.' }
gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Run gh auth login and try again.' }
if (-not (Test-Path '.git')) { git init -b main }
$origin = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0 -and $origin -notmatch '/Albert-bit07/KONJE(\.git)?$') {
  throw 'Existing git origin is not the intended KONJE repository. Aborting.'
}
# Explicit file allowlist; NEVER add reference/, images, keys, databases or secrets.
$allowed = @('CMakeLists.txt', '.gitignore', '.env.example', 'README.md', 'ATTRIBUTION.md',
             '.github', 'src', 'include', 'tests', 'tools', 'scripts', 'docs', 'config')
git add -- $allowed
if ($LASTEXITCODE -ne 0) { throw 'git add failed' }
Write-Host 'Review the staged files. There must be no real images, keys or biometrics:'
git diff --cached --name-only
Write-Host 'If anything sensitive appears, answer NO.'
$approval = Read-Host 'Create PRIVATE Albert-bit07/KONJE repo and push these files? (type YES)'
if ($approval -cne 'YES') { throw 'Cancelled; nothing pushed.' }
git commit -m 'Bootstrap KONJE privacy-first C++20 prototype'
if ($LASTEXITCODE -ne 0) { throw 'Commit failed; inspect git status' }
gh repo create Albert-bit07/KONJE --private --source . --remote origin --push
if ($LASTEXITCODE -ne 0) { throw 'GitHub repo creation/push failed; repository may have been created. Check gh repo view.' }
Write-Host 'Private KONJE repository created and pushed. Confirm visibility on GitHub.'