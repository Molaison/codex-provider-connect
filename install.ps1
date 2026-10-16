# Published at releases/latest/download/install.ps1; payloads stay on one release.
# codex-provider-connect: user-local native Windows bootstrap; no administrator needed.
param([string]$Url = $env:CODEX_PROVIDER_URL, [switch]$Repair, [switch]$Reconfigure, [switch]$RestartIfIdle)

& {
    param([string]$ProviderUrl, [bool]$DoRepair, [bool]$DoReconfigure, [bool]$DoRestartIfIdle)
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue'
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    if (-not [Environment]::Is64BitOperatingSystem) { throw '64-bit Windows is required.' }

    $Release = if ($env:CODEX_CONNECT_REF) { $env:CODEX_CONNECT_REF } else { 'v0.1.9' }
    $Base = if ($env:CODEX_CONNECT_BASE) { $env:CODEX_CONNECT_BASE } elseif ($env:CODEX_CONNECT_REF) {
        "https://raw.githubusercontent.com/Molaison/codex-provider-connect/$Release"
    } else { "https://github.com/Molaison/codex-provider-connect/releases/download/$Release" }
    $Root = Join-Path $env:LOCALAPPDATA 'codex-provider-connect'
    $Bin = Join-Path $env:USERPROFILE '.local\bin'
    $Launcher = Join-Path $Bin 'codex.exe'
    $Python = Join-Path $Root 'python\python.exe'
    $Helper = Join-Path $Root 'codex_provider.py'
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
        $Catalog = Join-Path $Temporary 'model_catalog.json'
        Invoke-WebRequest -UseBasicParsing -Uri "$Base/model_catalog.json" -OutFile $Catalog
        $Parsed = Get-Content -Raw -LiteralPath $Catalog | ConvertFrom-Json
        if (-not $Parsed.models -or $Parsed.models.Count -eq 0) { throw 'Invalid model catalog; existing setup was not replaced.' }
        Move-Item -Force -LiteralPath $Catalog -Destination (Join-Path $Root 'model_catalog.json')
        Move-Item -Force -LiteralPath $Download -Destination $Helper
        $Arguments = @('_native-setup')
        if ($DoRepair) { $Arguments += '--repair' }
        if ($DoReconfigure) { $Arguments += '--reconfigure' }
        if ($DoRestartIfIdle) { $Arguments += '--restart-if-idle' }
        if ($ProviderUrl) { $Arguments += @('--url', $ProviderUrl) }
        & $Python -X utf8 $Helper @Arguments
        if ($LASTEXITCODE -ne 0) { throw 'Setup is not verified. Re-run the same fixed download command; no READY was issued.' }
        $Current = [Environment]::GetEnvironmentVariable('Path', 'User')
        if (($Current -split ';') -notcontains $Bin) { [Environment]::SetEnvironmentVariable('Path', "$Bin;$Current", 'User') }
        $env:Path = "$Bin;$env:Path"
        Write-Host "`n[READY] Native configuration, model menu, and real read-only tool check passed."
        Write-Host "Start: & `"$Launcher`" (or codex in a new terminal)"
        Write-Host 'Install, update, or repair: re-run the same fixed download command; add -Reconfigure to change the key.'
        Write-Host 'Passed checks are reused; add -Repair only to force a new check.'

    }
    finally {
        Remove-Item -LiteralPath $Temporary -Recurse -Force
    }
} $Url ([bool]$Repair) ([bool]$Reconfigure) ([bool]$RestartIfIdle)
