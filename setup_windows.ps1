$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$HostDir = Join-Path $Root "host"
$Req = Join-Path $HostDir "requirements_asr.txt"
$RuntimeRoot = Join-Path $Root ".runtime"
$arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
$Venv = Join-Path $RuntimeRoot ("envs\windows-" + $arch + "\venv")
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$HostExe = Join-Path $Venv "Scripts\bilisum-native-host.exe"
New-Item -ItemType Directory -Force -Path (Split-Path $Venv) | Out-Null

function Step([string]$Text) { Write-Host ""; Write-Host "==> $Text" -ForegroundColor Cyan }
function Fail([string]$Text) { Write-Host "ERROR: $Text" -ForegroundColor Red; exit 1 }
function Test-OllamaApi { try { Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null; return $true } catch { return $false } }
function Find-Ollama { $c=Get-Command ollama.exe -ErrorAction SilentlyContinue; if($c){return $c.Source}; $p=Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"; if(Test-Path $p){return $p}; return $null }
function Get-MemoryGB { try { return [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB) } catch { return 0 } }
function Get-UsableModel([object[]]$Models) { foreach($m in $Models){ $name=if($m.name){[string]$m.name}elseif($m.model){[string]$m.model}else{""}; if($name -match '(?i)embed|rerank|cloud'){continue}; if($name -match '(?i)^(qwen3\.5|qwen3:|qwen2\.5|gemma3|llama3\.[123]|mistral|ministral|phi[34]|deepseek-r1|glm)'){return $name} }; return $null }
function Test-Python([string]$p){ if(-not $p -or -not (Test-Path $p)){return $false}; try { & $p -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] < (3,13) else 1)" 2>$null; return ($LASTEXITCODE -eq 0) } catch { return $false } }
function Find-Python { foreach($n in @("python.exe","python3.exe")){ $c=Get-Command $n -ErrorAction SilentlyContinue; if($c -and (Test-Python $c.Source)){return $c.Source} }; $py=Get-Command py.exe -ErrorAction SilentlyContinue; if($py){ foreach($s in @("-3.12","-3.11","-3.10")){ try{$p=& $py.Source $s -c "import sys;print(sys.executable)" 2>$null | Select-Object -Last 1; if($p -and (Test-Python $p.Trim())){return $p.Trim()}}catch{} } }; return $null }
function Find-Uv { $c=Get-Command uv.exe -ErrorAction SilentlyContinue; if($c){return $c.Source}; foreach($p in @((Join-Path $env:USERPROFILE ".local\bin\uv.exe"),(Join-Path $env:LOCALAPPDATA "uv\uv.exe"))){if(Test-Path $p){return $p}}; return $null }

$ram=Get-MemoryGB
if($ram -le 0){$DefaultModel="qwen3.5:2b"}elseif($ram -lt 6){$DefaultModel="qwen3.5:0.8b"}elseif($ram -lt 10){$DefaultModel="qwen3.5:2b"}else{$DefaultModel="qwen3.5:4b"}
Write-Host "BiliSum setup" -ForegroundColor White
Write-Host "Windows / $arch / ~$ram GB RAM. Existing compatible components are reused." -ForegroundColor DarkGray

Step "1/4 Ollama"
if(-not (Test-OllamaApi)){
  $ollama=Find-Ollama
  if($ollama){ Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden | Out-Null }
  else { Write-Host "Ollama not found. Installing the official Windows build..."; try { Invoke-RestMethod "https://ollama.com/install.ps1" | Invoke-Expression } catch { Fail "Ollama installation failed: $($_.Exception.Message)" }; $ollama=Find-Ollama }
  for($i=0;$i -lt 30 -and -not (Test-OllamaApi);$i++){Start-Sleep -Seconds 1}
}
if(-not (Test-OllamaApi)){Fail "Ollama is installed but not responding."}
$tags=Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 5
$usable=Get-UsableModel @($tags.models)
if($usable){Write-Host "Using existing model: $usable" -ForegroundColor Green}else{Write-Host "No suitable local model found. Downloading $DefaultModel" -ForegroundColor Yellow; $body=@{model=$DefaultModel;stream=$false}|ConvertTo-Json -Compress; Invoke-RestMethod "http://127.0.0.1:11434/api/pull" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 7200 | Out-Null}

Step "2/4 Local transcription runtime"
$runtimeOk=$false
if(Test-Path $VenvPython){try{& $VenvPython -c "import faster_whisper" 2>$null; if($LASTEXITCODE -eq 0){$runtimeOk=$true}}catch{}}
if(-not $runtimeOk){
  if(Test-Path $Venv){Remove-Item -Recurse -Force $Venv}
  $python=Find-Python
  if($python){ & $python -m venv $Venv 2>$null }
  if(-not (Test-Path $VenvPython)){
    $uv=Find-Uv
    if(-not $uv){$env:UV_NO_MODIFY_PATH="1"; Invoke-RestMethod "https://astral.sh/uv/install.ps1" | Invoke-Expression; $uv=Find-Uv}
    if(-not $uv){Fail "Could not prepare Python runtime."}
    & $uv venv --python ">=3.10,<3.13" $Venv
  }
  & $VenvPython -m pip install --disable-pip-version-check -r $Req
  if($LASTEXITCODE -ne 0){Fail "Could not install transcription dependencies."}
}

Step "3/4 BiliSum host"
& $VenvPython -m pip install --disable-pip-version-check --no-deps --editable $HostDir | Out-Null
if(-not (Test-Path $HostExe)){Fail "Native host launcher was not created."}
& $VenvPython (Join-Path $Root "scripts\register_native_host.py") --root $Root --host-executable $HostExe
if($LASTEXITCODE -ne 0){Fail "Could not register the browser native host."}
$schema = (Get-Content (Join-Path $Root "RUNTIME_SCHEMA") -Raw).Trim()
Set-Content -Path (Join-Path $RuntimeRoot "runtime_schema.txt") -Value $schema -Encoding UTF8

Step "4/4 Ready"
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "In Chrome/Edge: open chrome://extensions, enable Developer mode, choose Load unpacked, and select:" -ForegroundColor White
Write-Host (Join-Path $Root "extension") -ForegroundColor Cyan
Write-Host "Future portable releases can be checked and installed from BiliSum settings; models and caches are kept." -ForegroundColor DarkGray
