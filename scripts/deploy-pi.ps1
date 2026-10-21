# Run from Windows PowerShell in the KONJE repository root.
# Stages only source/configuration, never .env, biometrics, keys, or built artifacts.
param(
  [string]$Target = 'konje@konje.local',
  [string]$RemoteDir = '/home/konje/KONJE'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'CMakeLists.txt') -or -not (Test-Path 'src/main.cpp')) {
  throw 'Run this script from the root of the KONJE source repository.'
}
$files = @('CMakeLists.txt', 'src', 'include', 'tools', 'scripts', 'config', 'docs', 'tests', 'README.md', 'ATTRIBUTION.md')
ssh $Target "mkdir -p $RemoteDir"
if ($LASTEXITCODE -ne 0) { throw 'Could not create remote directory' }
foreach ($file in $files) {
  scp -r $file "${Target}:${RemoteDir}/"
  if ($LASTEXITCODE -ne 0) { throw "Transfer failed: $file" }
}
Write-Host 'Source staged on Pi. Run the build and tests through SSH:'
Write-Host "ssh $Target"
Write-Host "cd ~/KONJE && bash scripts/setup-pi.sh && cmake -S . -B build -G Ninja && cmake --build build && ctest --test-dir build --output-on-failure"