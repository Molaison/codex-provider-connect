# codex-provider-connect: user-local native Windows bootstrap; no administrator needed.
param([string]$Url = $env:CODEX_PROVIDER_URL)

& {
    param([string]$ProviderUrl)
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    if (-not [Environment]::Is64BitOperatingSystem) { throw '64-bit Windows is required.' }
    if (-not (Get-Command codex -ErrorAction SilentlyContinue)) { throw 'Install official Codex first and make codex available in PATH.' }

    $Release = if ($env:CODEX_CONNECT_REF) { $env:CODEX_CONNECT_REF } else { 'v0.1.3' }
    $Base = "https://raw.githubusercontent.com/Molaison/codex-provider-connect/$Release"
    $Root = Join-Path $env:LOCALAPPDATA 'codex-provider-connect'
    $Bin = Join-Path $env:USERPROFILE '.local\bin'
    $Launcher = Join-Path $Bin 'codex-provider.cmd'
    $Python = Join-Path $Root 'python\python.exe'
    $Helper = Join-Path $Root 'codex_provider.py'
    if ((Test-Path -LiteralPath $Launcher) -and -not ((Get-Content -Raw -LiteralPath $Launcher) -match 'codex-provider-connect')) {
        throw "Refusing to overwrite an unrelated file: $Launcher"
    }
    New-Item -ItemType Directory -Force -Path $Root, $Bin | Out-Null
    $Temporary = Join-Path ([IO.Path]::GetTempPath()) ('codex-provider-install-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $Temporary | Out-Null
    try {
        if (-not (Test-Path -LiteralPath $Python)) {
            $Archive = Join-Path $Temporary 'python.zip'
            $PythonUrl = 'https://www.python.org/ftp/python/3.13.7/python-3.13.7-embed-amd64.zip'
            $Expected = 'f6cca216a359be84797cabb54149ce5e062afb16cc7567eb7fc51cacb2d86b65'
            Invoke-WebRequest -UseBasicParsing -Uri $PythonUrl -OutFile $Archive
            if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash.ToLowerInvariant() -ne $Expected) {
                throw 'Python archive SHA256 mismatch; nothing was executed.'
            }
            Expand-Archive -LiteralPath $Archive -DestinationPath (Join-Path $Temporary 'python')
            Move-Item -LiteralPath (Join-Path $Temporary 'python') -Destination (Join-Path $Root 'python')
        }
        $Download = Join-Path $Temporary 'codex_provider.py'
        Invoke-WebRequest -UseBasicParsing -Uri "$Base/codex_provider.py" -OutFile $Download
        # 入口脚本自带默认版本；若它指向的载荷不是同一版本，宁可失败也不要静默装旧版。
        if ($Release -match '^v\d+\.\d+\.\d+$') {
            $ExpectedVersion = 'VERSION = "' + $Release.TrimStart('v') + '"'
            if (-not (Select-String -LiteralPath $Download -SimpleMatch $ExpectedVersion -Quiet)) {
                throw "Downloaded codex_provider.py does not match $Release; nothing was installed."
            }
        }
        Move-Item -Force -LiteralPath $Download -Destination $Helper
        $Lines = @('@echo off', 'rem codex-provider-connect', 'setlocal', 'set "PYTHONUTF8=1"', '"%LOCALAPPDATA%\codex-provider-connect\python\python.exe" "%LOCALAPPDATA%\codex-provider-connect\codex_provider.py" %*', 'exit /b %errorlevel%')
        [IO.File]::WriteAllLines($Launcher, $Lines, [Text.Encoding]::ASCII)
        $Arguments = @('configure')
        if ($ProviderUrl) { $Arguments += @('--url', $ProviderUrl) }
        & $Python -X utf8 $Helper @Arguments
        if ($LASTEXITCODE -ne 0) { throw 'Provider configuration failed; existing Codex configuration was not changed.' }
        Write-Host "`nStart official Codex with automatic catalog refresh:"
        Write-Host "& `"$Launcher`""
        Write-Host 'No system PATH change and no existing session restart.'
    }
    finally {
        Remove-Item -LiteralPath $Temporary -Recurse -Force
    }
} $Url
