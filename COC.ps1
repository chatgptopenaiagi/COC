[CmdletBinding()]
param(
 [Parameter(Position=0)][ValidateSet('BUILD','TEST','VERIFY','START','STOP','STATUS','DOCTOR','RECOVER','PACKAGE','OPEN','INSTALL')][string]$Command='STATUS',
 [switch]$Demo,[switch]$Codex,[int]$Port=7310
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$python=Join-Path $PSScriptRoot $(if($IsWindows){'.venv/Scripts/python.exe'}else{'.venv/bin/python'})
function Invoke-Checked([string]$Program,[string[]]$Arguments) {
 & $Program @Arguments
 if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
switch ($Command) {
 'INSTALL' {
   if (!(Test-Path -LiteralPath $python)) { Invoke-Checked 'python' @('-m','venv','.venv') }
   if(Test-Path RELEASE-MANIFEST.json) {
     $wheel=@(Get-ChildItem dist/python -Filter '*.whl')[0].FullName
     Invoke-Checked $python @('-m','pip','install','--no-index','--find-links','dist/wheelhouse',$wheel)
   } else {
     Invoke-Checked $python @('-m','pip','install','-r','requirements-dev.lock')
     Invoke-Checked $python @('-m','pip','install','-e','kernels/python')
     Invoke-Checked 'npm' @('ci')
   }
 }
 'BUILD' { & ./scripts/build.ps1 }
 'TEST' { & ./scripts/test.ps1 }
 'VERIFY' { & ./scripts/build.ps1; & ./scripts/test.ps1; Invoke-Checked $python @('scripts/scan-secrets.py'); Invoke-Checked $python @('scripts/acceptance-report.py') }
 'PACKAGE' { Invoke-Checked $python @('scripts/scan-secrets.py'); Invoke-Checked $python @('scripts/package.py') }
 default {
   $arguments=@('-m','coc.control',$Command.ToLowerInvariant(),'--root',$PSScriptRoot)
   if ($Command -eq 'START') { $arguments+=@('--port',"$Port"); if($Demo){$arguments+='--demo'}; if($Codex){$arguments+='--codex'} }
   Invoke-Checked $python $arguments
 }
}
