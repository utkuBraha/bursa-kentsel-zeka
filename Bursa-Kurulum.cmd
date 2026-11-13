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
    if (!(Test-Path (Join-Path $here 'docker-compose.yml'))) {
        $project = Join-Path $base 'bursa-kentsel-zeka-main'
        if (!(Test-Path (Join-Path $project 'docker-compose.yml'))) {
            New-Item -ItemType Directory -Force -Path $base | Out-Null
            $temp = Join-Path $env:TEMP ('bursa-' + [guid]::NewGuid())
            New-Item -ItemType Directory -Path $temp | Out-Null
            try {
                Write-Host 'Bursa Kentsel Zeka indiriliyor...'
                $archive = Join-Path $temp 'project.zip'
                Invoke-WebRequest -UseBasicParsing -Uri 'https://codeload.github.com/utkuBraha/bursa-kentsel-zeka/zip/refs/heads/main' -OutFile $archive
                Expand-Archive -LiteralPath $archive -DestinationPath $temp
                Move-Item -LiteralPath (Join-Path $temp 'bursa-kentsel-zeka-main') -Destination $project
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
    Write-Host 'Uygulama ve demo verisi hazirlaniyor. Ilk acilis birkac dakika surebilir.'
    docker compose up --build -d --wait --wait-timeout 600
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose uygulamayi baslatamadi.' }
    Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/health/ready' | Out-Null
    Start-Process 'http://127.0.0.1:3016/'
    exit 0
} catch {
    Write-Host $_.Exception.Message
    exit 1
}
