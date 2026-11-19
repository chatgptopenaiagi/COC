$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$python=Join-Path $root '.venv/Scripts/python.exe'
if (!$IsWindows) {$python=Join-Path $root '.venv/bin/python'}
$cargo='cargo'
if(Test-Path .tools/cargo/bin/cargo.exe){$env:RUSTUP_HOME=Join-Path $root '.tools/rustup';$env:CARGO_HOME=Join-Path $root '.tools/cargo';$cargo=Join-Path $root '.tools/cargo/bin/cargo.exe'}
New-Item -ItemType Directory -Path dist,evidence/builds -Force | Out-Null
$results=[System.Collections.Generic.List[object]]::new()
function Build-Step([string]$Name,[string]$Program,[string[]]$Arguments) {
 $timer=[System.Diagnostics.Stopwatch]::StartNew()
 & $Program @Arguments 2>&1 | Tee-Object -FilePath (Join-Path $root "evidence/builds/$Name.log")
 $code=$LASTEXITCODE
 $results.Add([ordered]@{component=$Name;status=if($code -eq 0){'PASS'}else{'FAIL'};exit_code=$code;seconds=$timer.Elapsed.TotalSeconds})
 if($code -ne 0){throw "$Name build failed: $code"}
}
try {
 Push-Location kernels/go
 try {Build-Step 'go' 'go' @('build','-trimpath','-o',(Join-Path $root $(if($IsWindows){'dist/coc-broker.exe'}else{'dist/coc-broker'})),'./cmd/coc-broker')} finally {Pop-Location}
 Build-Step 'rust' $cargo @('build','--locked','--manifest-path','kernels/rust/Cargo.toml')
 Build-Step 'rust-release' $cargo @('build','--release','--locked','--manifest-path','kernels/rust/Cargo.toml')
 Build-Step 'typescript' 'npm' @('run','build')
 Build-Step 'java' 'pwsh' @('-NoProfile','-File','scripts/build-java.ps1')
 Build-Step 'python' $python @('-m','build','kernels/python','--outdir','dist/python')
 $env:COC_DJANGO_SECRET=[Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(48))
 Build-Step 'django' $python @('frameworks/django/manage.py','check')
} finally {
 $results | ConvertTo-Json -Depth 5 | Set-Content evidence/builds/latest.json -Encoding utf8
 Remove-Item Env:COC_DJANGO_SECRET -ErrorAction SilentlyContinue
}
