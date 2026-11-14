@echo off
setlocal
set "BURSA_INSTALLER=%~f0"
powershell.exe -NoLogo -NoProfile -Command "$lines=Get-Content -LiteralPath $env:BURSA_INSTALLER; $start=[Array]::IndexOf($lines,':POWERSHELL'); & ([scriptblock]::Create(($lines[($start+1)..($lines.Length-1)] -join [Environment]::NewLine)))"
if errorlevel 1 (
    echo Kurulum tamamlanamadi. Yukaridaki mesaji kontrol edin.
    pause
    exit /b 1
)
exit /b 0
:POWERSHELL
$ErrorActionPreference = 'Stop'
try {
    $base = Join-Path $env:LOCALAPPDATA 'Bursa Kentsel Zeka'
    $here = Split-Path $env:BURSA_INSTALLER
    $project = $here
    if (!(Test-Path (Join-Path $here 'compose.desktop.yml'))) {
        $project = Join-Path $base 'bursa-kentsel-zeka-osrm'
        if (!(Test-Path (Join-Path $project 'compose.desktop.yml'))) {
            New-Item -ItemType Directory -Force -Path $base | Out-Null
            $temp = Join-Path $env:TEMP ('bursa-' + [guid]::NewGuid())
            New-Item -ItemType Directory -Path $temp | Out-Null
            try {
                Write-Host 'Bursa Kentsel Zeka indiriliyor...'
                $archive = Join-Path $temp 'project.zip'
                Invoke-WebRequest -UseBasicParsing -Uri 'https://codeload.github.com/utkuBraha/bursa-kentsel-zeka/zip/refs/heads/main' -OutFile $archive
                Expand-Archive -LiteralPath $archive -DestinationPath $temp
                $source = Join-Path $temp 'bursa-kentsel-zeka-main'
                if (!(Test-Path (Join-Path $source 'compose.desktop.yml'))) {
                    throw 'Indirilen arsiv arac agi kurulum dosyalarini icermiyor.'
                }
                Move-Item -LiteralPath $source -Destination $project
            } finally {
                Remove-Item -LiteralPath $temp -Recurse -Force
            }
        }
    }

    $dockerPaths = @(
        (Join-Path $env:ProgramFiles 'Docker\Docker'),
        (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop')
    )
    function Find-DockerDesktop {
        foreach ($path in $dockerPaths) {
            $desktop = Join-Path $path 'Docker Desktop.exe'
            if (Test-Path $desktop) {
                $env:Path = (Join-Path $path 'resources\bin') + ';' + $env:Path
                return $desktop
            }
        }
    }
    function Test-DockerEngine {
        if (!(Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
        cmd.exe /d /c 'docker info >nul 2>&1'
        return $LASTEXITCODE -eq 0
    }

    $desktop = Find-DockerDesktop
    if (!(Test-DockerEngine) -and !$desktop) {
        $arch = $env:PROCESSOR_ARCHITECTURE
        if ($env:PROCESSOR_ARCHITEW6432) { $arch = $env:PROCESSOR_ARCHITEW6432 }
        if ($arch -ne 'AMD64' -and $arch -ne 'ARM64') {
            throw 'Bu Windows islemcisi desteklenmiyor.'
        }
        New-Item -ItemType Directory -Force -Path $base | Out-Null
        $installer = Join-Path $base 'Docker Desktop Installer.exe'
        Write-Host 'Docker Desktop indiriliyor...'
        Invoke-WebRequest -UseBasicParsing -Uri "https://desktop.docker.com/win/main/$($arch.ToLowerInvariant())/Docker%20Desktop%20Installer.exe" -OutFile $installer
        $signature = Get-AuthenticodeSignature -LiteralPath $installer
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Docker') {
            throw 'Docker kurulum dosyasinin imzasi dogrulanamadi.'
        }
        Start-Process -FilePath $installer -Wait
        $desktop = Find-DockerDesktop
    }

    if (!(Test-DockerEngine)) {
        if (!$desktop) { throw 'Docker Desktop kurulumu bulunamadi. Yeniden baslatma gerekiyorsa tamamlayip bu dosyayi tekrar acin.' }
        Start-Process -FilePath $desktop
        Write-Host 'Docker Desktop hazir olana kadar bekleniyor...'
        for ($attempt = 0; $attempt -lt 90; $attempt++) {
            if (Test-DockerEngine) { break }
            Start-Sleep -Seconds 2
        }
        if (!(Test-DockerEngine)) { throw 'Docker Desktop hazir degil. Ilk acilis ve WSL 2 adimlarini tamamlayip dosyayi tekrar acin.' }
    }

    Set-Location -LiteralPath $project
    if (!(Test-Path '.env')) { Copy-Item '.env.example' '.env' }
    $composeArgs = @('compose', '-f', 'docker-compose.yml', '-f', 'compose.desktop.yml')

    # Free this project's own ports first, then pick a free host port for each service.
    cmd.exe /d /c 'docker compose -f docker-compose.yml -f compose.desktop.yml stop >nul 2>&1'
    $dockerPorts = (docker ps --format '{{.Ports}}') -join "`n"
    $excludedPorts = @(netsh interface ipv4 show excludedportrange protocol=tcp | ForEach-Object {
        if ($_ -match '^\s*(\d+)\s+(\d+)\s*\*?\s*$') {
            [pscustomobject]@{ First = [int]$Matches[1]; Last = [int]$Matches[2] }
        }
    })
    function Test-PortBusy([int]$port) {
        foreach ($range in $excludedPorts) {
            if ($port -ge $range.First -and $port -le $range.Last) { return $true }
        }
        if ($dockerPorts -match "(:|^)$port->") { return $true }
        $client = New-Object System.Net.Sockets.TcpClient
        try {
            $connect = $client.BeginConnect('127.0.0.1', $port, $null, $null)
            return ($connect.AsyncWaitHandle.WaitOne(500) -and $client.Connected)
        } catch { return $false } finally { $client.Close() }
    }
    function Get-EnvPort([string]$name) {
        $line = Get-Content '.env' | Where-Object { $_ -match "^$name=\d+$" } | Select-Object -Last 1
        if ($line) { return [int]($line -split '=')[1] }
    }
    function Select-Port([string]$name, [int]$default, [int]$start = 0) {
        $saved = Get-EnvPort $name
        $port = if ($start) { $start } elseif ($saved) { $saved } else { $default }
        for ($attempt = 0; $attempt -lt 50; $attempt++) {
            if (!(Test-PortBusy $port)) {
                if ($port -ne $saved) {
                    $lines = @(Get-Content '.env' | Where-Object { $_ -notmatch "^$name=" }) + "$name=$port"
                    Set-Content -LiteralPath '.env' -Value $lines -Encoding ASCII
                }
                Set-Item -Path "Env:$name" -Value "$port"
                return $port
            }
            Write-Host "Port $port kullanimda, sonraki port deneniyor..."
            $port++
        }
        throw "$name icin bos port bulunamadi."
    }
    $appPort = Select-Port 'BURSA_APP_PORT' 3016
    Select-Port 'BURSA_API_PORT' 8000 | Out-Null
    Select-Port 'BURSA_DB_PORT' 5433 | Out-Null

    Write-Host 'Uygulama ve demo verisi hazirlaniyor. Ilk acilis birkac dakika surebilir.'
    # Docker can hold a port that no host tool shows; move to the next port and retry.
    $started = $false
    for ($try = 0; $try -lt 5; $try++) {
        $output = cmd.exe /d /c 'docker compose -f docker-compose.yml -f compose.desktop.yml up --build -d --wait --wait-timeout 600 2>&1'
        $output | ForEach-Object { Write-Host $_ }
        if ($LASTEXITCODE -eq 0) { $started = $true; break }
        $match = [regex]::Match(($output -join "`n"), 'Bind for \S*:(\d+) failed: port is already allocated|exposing port TCP [^\s:]*:(\d+)')
        if (!$match.Success) { break }
        $busy = [int]($match.Groups[1].Value + $match.Groups[2].Value)
        $name = @('BURSA_APP_PORT', 'BURSA_API_PORT', 'BURSA_DB_PORT') | Where-Object { (Get-Item "Env:$_").Value -eq "$busy" } | Select-Object -First 1
        if (!$name) { break }
        Write-Host "Port $busy Docker tarafindan kullaniliyor, sonraki port deneniyor..."
        $port = Select-Port $name $busy ($busy + 1)
        if ($name -eq 'BURSA_APP_PORT') { $appPort = $port }
    }
    if (!$started) {
        & docker @composeArgs ps -a
        & docker @composeArgs logs --tail 40 api frontend osrm
        throw 'Docker Compose uygulamayi baslatamadi.'
    }
    & docker @composeArgs exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready', timeout=15)"
    if ($LASTEXITCODE -ne 0) { throw 'API hazir degil.' }
    & docker @composeArgs exec -T api python -c "import json, urllib.request; result = json.load(urllib.request.urlopen('http://osrm:5000/nearest/v1/driving/28.9427163,40.2103735', timeout=15)); assert result['code'] == 'Ok' and result['waypoints']"
    if ($LASTEXITCODE -ne 0) { throw 'Arac agi servisi dogrulanamadi.' }
    Write-Host "Uygulama hazir: http://127.0.0.1:$appPort/"
    Start-Process "http://127.0.0.1:$appPort/"
    exit 0
} catch {
    Write-Host $_.Exception.Message
    exit 1
}
