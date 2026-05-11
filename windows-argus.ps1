# start-argus.ps1
# start with: powershell -ExecutionPolicy Bypass -File windows-argus.ps1
# add `up` to start containers and `--build` for the first build.
#
# URL flags mirror argus.sh:
#   -UpdateApiUrl     rewrite VITE_API_URL to the current local IP
#   -UpdateWebodmUrl  rewrite WEBODM_URL to the current local IP (port 8000)
#   -UpdateAllUrls    both of the above
#   -KeepApiUrl       keep VITE_API_URL as-is (overrides ARGUS_DEFAULT_FLAGS)
#   -KeepWebodmUrl    keep WEBODM_URL as-is (overrides ARGUS_DEFAULT_FLAGS)
#   -KeepUrls         keep both URLs as-is
#
# .env knobs:
#   ARGUS_DEFAULT_FLAGS  flag string always prepended on launch. Example:
#                        ARGUS_DEFAULT_FLAGS=--update-all-urls


#######################################
# Parse CLI args
#######################################

param(
    [switch]$UpdateApiUrl,
    [switch]$UpdateWebodmUrl,
    [switch]$UpdateAllUrls,
    [switch]$KeepApiUrl,
    [switch]$KeepWebodmUrl,
    [switch]$KeepUrls,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ComposeArgs
)

$ErrorActionPreference = "Stop"


#######################################
# Resolve Argus path
#######################################
$ARGUS_PATH = $PSScriptRoot
Write-Host "Argus path: $ARGUS_PATH"


#######################################
# Create .env if missing
#######################################
$envFile     = Join-Path $ARGUS_PATH ".env"
$exampleFile = Join-Path $ARGUS_PATH ".env.example"

if (-not (Test-Path $envFile)) {
    Write-Host "Creating .env from example..."
    Copy-Item $exampleFile $envFile
    Write-Host "Edit .env before first run."
}

#######################################
# Sync missing keys from .env.example into .env
# Non-destructive: existing keys are never touched. Keys present in
# .env.example but absent from .env are appended verbatim so the user
# can fill in values that need them.
#######################################
function Sync-EnvWithExample {
    param(
        [string]$Example,
        [string]$EnvFile
    )

    if (-not (Test-Path $Example)) { return }

    $existingKeys = @{}
    foreach ($line in (Get-Content $EnvFile)) {
        if ($line -match "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=") {
            $existingKeys[$matches[1]] = $true
        }
    }

    # Ensure .env ends with a newline before we append, otherwise Add-Content
    # would concatenate the first new key onto the existing last line.
    $rawBytes = [System.IO.File]::ReadAllBytes($EnvFile)
    if ($rawBytes.Length -gt 0 -and $rawBytes[$rawBytes.Length - 1] -ne 0x0A) {
        [System.IO.File]::AppendAllText($EnvFile, [Environment]::NewLine)
    }

    $added = 0
    foreach ($line in (Get-Content $Example)) {
        if ($line -match "^\s*$" -or $line -match "^\s*#") { continue }
        if ($line -match "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=") {
            $key = $matches[1]
            if (-not $existingKeys.ContainsKey($key)) {
                Add-Content -Path $EnvFile -Value $line
                Write-Host "  Added missing key from .env.example: $key"
                $added++
            }
        }
    }

    if ($added -gt 0) {
        Write-Host "Added $added new key(s) to .env. Edit them if any need values before re-running."
    }
}
Sync-EnvWithExample -Example $exampleFile -EnvFile $envFile

#######################################
# Load .env
#######################################
Get-Content $envFile | ForEach-Object {
    if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
        $name = $matches[1]
        $value = $matches[2]
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

#######################################
# Merge ARGUS_DEFAULT_FLAGS into the resolved switches
# CLI switches take precedence (they were already set when -or'd below).
#######################################
$defaultFlags = $env:ARGUS_DEFAULT_FLAGS
if ($defaultFlags) {
    Write-Host "Applying ARGUS_DEFAULT_FLAGS: $defaultFlags"
    foreach ($flag in $defaultFlags -split '\s+') {
        switch ($flag) {
            "--update-api-url"    { $UpdateApiUrl    = $true }
            "--update-webodm-url" { $UpdateWebodmUrl = $true }
            "--update-all-urls"   { $UpdateAllUrls   = $true }
            "--keep-api-url"      { $KeepApiUrl      = $true }
            "--keep-webodm-url"   { $KeepWebodmUrl   = $true }
            "--keep-urls"         { $KeepUrls        = $true }
            ""                    { }
            default {
                Write-Warning "ARGUS_DEFAULT_FLAGS: unknown flag '$flag' ignored."
            }
        }
    }
}

# Resolve effective update intent. --keep-* always wins over --update-*.
$doUpdateApi    = $UpdateApiUrl    -or $UpdateAllUrls
$doUpdateWebodm = $UpdateWebodmUrl -or $UpdateAllUrls
if ($KeepApiUrl    -or $KeepUrls) { $doUpdateApi    = $false }
if ($KeepWebodmUrl -or $KeepUrls) { $doUpdateWebodm = $false }

Write-Host "Effective: UpdateApi=$doUpdateApi UpdateWebodm=$doUpdateWebodm  ComposeArgs=$ComposeArgs"


#######################################
# Detect local IP
#######################################
$LOCAL_IP = Get-NetIPAddress `
    -AddressFamily IPv4 `
    -InterfaceAlias "Ethernet*" `
    -ErrorAction SilentlyContinue |
    Where-Object {$_.IPAddress -notlike "169.254*"} |
    Select-Object -First 1 -ExpandProperty IPAddress

if (-not $LOCAL_IP) {
    Write-Warning "Could not determine local IP, falling back to 127.0.0.1"
    $LOCAL_IP = "127.0.0.1"
}

$PORT_API = $env:PORT_API
if (-not $PORT_API) { $PORT_API = 8008 }

$COMPUTED_VITE_API_URL = "http://$LOCAL_IP`:$PORT_API"
$COMPUTED_WEBODM_URL   = "http://$LOCAL_IP`:8000"


#######################################
# Update VITE_API_URL
#######################################
$envText = Get-Content $envFile

if (-not $env:VITE_API_URL) {
    Write-Host "VITE_API_URL not set, initializing to $COMPUTED_VITE_API_URL"
    if ($envText -match "^VITE_API_URL=") {
        $envText = $envText -replace "^VITE_API_URL=.*", "VITE_API_URL=$COMPUTED_VITE_API_URL"
    } else {
        $envText += "VITE_API_URL=$COMPUTED_VITE_API_URL"
    }
    Set-Content $envFile $envText
    $env:VITE_API_URL = $COMPUTED_VITE_API_URL
} elseif ($doUpdateApi) {
    Write-Host "Updating VITE_API_URL to $COMPUTED_VITE_API_URL"
    $envText = $envText -replace "^VITE_API_URL=.*", "VITE_API_URL=$COMPUTED_VITE_API_URL"
    Set-Content $envFile $envText
    $env:VITE_API_URL = $COMPUTED_VITE_API_URL
} else {
    Write-Host "VITE_API_URL is set to $env:VITE_API_URL (use -UpdateApiUrl to override with local IP)"
}


#######################################
# Update WEBODM_URL
#######################################
$envText = Get-Content $envFile

if (-not $env:WEBODM_URL) {
    Write-Host "WEBODM_URL not set, initializing to $COMPUTED_WEBODM_URL"
    if ($envText -match "^WEBODM_URL=") {
        $envText = $envText -replace "^WEBODM_URL=.*", "WEBODM_URL=$COMPUTED_WEBODM_URL"
    } else {
        $envText += "WEBODM_URL=$COMPUTED_WEBODM_URL"
    }
    Set-Content $envFile $envText
    $env:WEBODM_URL = $COMPUTED_WEBODM_URL
} elseif ($doUpdateWebodm) {
    Write-Host "Updating WEBODM_URL to $COMPUTED_WEBODM_URL"
    $envText = $envText -replace "^WEBODM_URL=.*", "WEBODM_URL=$COMPUTED_WEBODM_URL"
    Set-Content $envFile $envText
    $env:WEBODM_URL = $COMPUTED_WEBODM_URL
} else {
    Write-Host "WEBODM_URL is set to $env:WEBODM_URL (use -UpdateWebodmUrl to override with local IP)"
}


#######################################
# GPU Detection (NVIDIA)
#######################################
$GPU_TYPE = "cpu"
Write-Host "Checking for NVIDIA GPU..."

if (Get-Command "nvidia-smi.exe" -ErrorAction SilentlyContinue) {
    Write-Host "NVIDIA GPU detected."

    $dockerInfo = docker info --format '{{json .Runtimes}}' | ConvertFrom-Json
    if ($dockerInfo.PSObject.Properties.Name -contains "nvidia") {
        $GPU_TYPE = "nvidia"
        Write-Host "NVIDIA container runtime found → GPU mode enabled."
    } else {
        Write-Host "NVIDIA GPU present but missing container runtime → CPU mode."
    }
} else {
    Write-Host "No NVIDIA GPU detected → CPU mode."
}

Write-Host "Final GPU type: $GPU_TYPE"

# #######################################
# # WebODM (optional) — service start not yet ported to Windows.
# # The URL handling above is active so containers see WEBODM_URL.
# #######################################
# $ENABLE_WEBODM = $env:ENABLE_WEBODM -eq "true"
# $WEBODM_PATH = $env:WEBODM_PATH
# if (-not $WEBODM_PATH) {
#     $WEBODM_PATH = "$HOME\WebODM"
# }
#
# $WEBODM_STARTED = $false
#
# if ($ENABLE_WEBODM -and (Test-Path "$WEBODM_PATH\webodm.sh")) {
#     Write-Host "Starting WebODM..."
#
#     Push-Location $WEBODM_PATH
#     & bash ./webodm.sh start
#     Pop-Location
#
#     $WEBODM_STARTED = $true
# }
#
# #######################################
# # Cleanup handler
# #######################################
# Register-EngineEvent PowerShell.Exiting -Action {
#     if ($WEBODM_STARTED) {
#         Write-Host "Stopping WebODM..."
#         Push-Location $WEBODM_PATH
#         & bash ./webodm.sh stop
#         Pop-Location
#     }
# }

#######################################
# Docker Compose selection
#######################################
$composeFiles = @(
    "-f", "$ARGUS_PATH\docker-compose.yml"
)

if ($GPU_TYPE -eq "nvidia") {
    $composeFiles += "-f"
    $composeFiles += "$ARGUS_PATH\docker-compose.nvidia.yml"
}

#######################################
# Run docker compose
#######################################
Write-Host "Running docker compose $composeFiles $ComposeArgs"
docker compose @composeFiles @ComposeArgs
