$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$deps = Join-Path $root '.tools/java'
$out = Join-Path $root 'sdk/java/build/classes'
New-Item -ItemType Directory -Path $deps,$out -Force | Out-Null
$libraries = @{
 'gson-2.13.2.jar' = 'https://repo.maven.apache.org/maven2/com/google/code/gson/gson/2.13.2/gson-2.13.2.jar'
 'h2-2.3.232.jar' = 'https://repo.maven.apache.org/maven2/com/h2database/h2/2.3.232/h2-2.3.232.jar'
}
foreach ($name in $libraries.Keys) { $target=Join-Path $deps $name; if (!(Test-Path -LiteralPath $target)) { Invoke-WebRequest $libraries[$name] -OutFile $target } }
$sources = @(Get-ChildItem -LiteralPath (Join-Path $root 'sdk/java/src/main/java') -Recurse -Filter '*.java' | ForEach-Object FullName)
& javac --release 21 -cp (Join-Path $deps '*') -d $out @sources
if ($LASTEXITCODE) { throw 'Java compilation failed' }
$javaInfo = & java -XshowSettings:properties -version 2>&1 | Out-String
$jdkDirectory = [regex]::Match($javaInfo, 'java.home = ([^\r\n]+)').Groups[1].Value.Trim()
$jar=Join-Path $jdkDirectory $(if($IsWindows){'bin/jar.exe'}else{'bin/jar'})
& $jar --create --file (Join-Path $root 'sdk/java/build/coc-java-sdk.jar') -C $out .
if ($LASTEXITCODE) { throw 'Java packaging failed' }
& java -cp ($out+[System.IO.Path]::PathSeparator+$deps+'/*') io.coc.EnterpriseHost self-test (Join-Path $root 'specifications/schemas/message.schema.json')
if ($LASTEXITCODE) { throw 'Java contract test failed' }
