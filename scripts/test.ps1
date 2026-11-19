$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$python=Join-Path $root '.venv/Scripts/python.exe'
if(!$IsWindows){$python=Join-Path $root '.venv/bin/python'}
$cargo='cargo'
if(Test-Path .tools/cargo/bin/cargo.exe){$env:RUSTUP_HOME=Join-Path $root '.tools/rustup';$env:CARGO_HOME=Join-Path $root '.tools/cargo';$cargo=Join-Path $root '.tools/cargo/bin/cargo.exe'}
New-Item -ItemType Directory -Path evidence/tests,.runtime -Force | Out-Null
# Default verification never spends API credits or launches inference.
foreach($name in @('COC_LIVE_OPENAI','COC_LIVE_CODEX','COC_LIVE_CODEX_ACCOUNTING','COC_LIVE_EXISTING','COC_LIVE_CODEX_CANCEL')){Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue}
$results=[System.Collections.Generic.List[object]]::new()
function Test-Step([string]$Name,[string]$Program,[string[]]$Arguments) {
 & $Program @Arguments 2>&1 | Tee-Object -FilePath (Join-Path $root "evidence/tests/$Name.log")
 $code=$LASTEXITCODE
 $results.Add([ordered]@{suite=$Name;status=if($code -eq 0){'PASS'}else{'FAIL'};exit_code=$code})
 if($code -ne 0){throw "$Name tests failed: $code"}
}
try {
 Push-Location kernels/go
 try {Test-Step 'go' 'go' @('test','-count=1','./...')} finally{Pop-Location}
 Test-Step 'rust' $cargo @('test','--locked','--manifest-path','kernels/rust/Cargo.toml')
 Test-Step 'javascript-typescript' 'npm' @('test')
 Test-Step 'java' 'pwsh' @('-NoProfile','-File','scripts/build-java.ps1')
 $temp=Join-Path $root ('.runtime/verification-'+[guid]::NewGuid().ToString('N'))
 if(!([System.IO.Path]::GetFullPath($temp)).StartsWith((Join-Path $root '.runtime')+[System.IO.Path]::DirectorySeparatorChar)){throw 'Invalid test workspace'}
 Test-Step 'python-all' $python @('-m','pytest','tests','-q',"--basetemp=$temp",'--junitxml=evidence/tests/full-regression.xml')
} finally {$results | ConvertTo-Json -Depth 5 | Set-Content evidence/tests/latest.json -Encoding utf8}
