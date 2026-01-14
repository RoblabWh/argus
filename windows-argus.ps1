# start-argus.ps1
# start with: powershell -ExecutionPolicy Bypass -File windows-argus.ps1
# add up to start container and --build for initial build


#######################################
# Parse CLI args
#######################################

param(
    [switch]$KeepIp,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ComposeArgs
)

# Default behavior
$FORCE_UPDATE_IP = -not $KeepIp
$ErrorActionPreference = "Stop"

Write-Host "Args parsed to: $ComposeArgs and FORCE_UPDATE_IP is set to $FORCE_UPDATE_IP"


#######################################
# Resolve Argus path
#######################################
$ARGUS_PATH = $PSScriptRoot
Write-Host "Argus path: $ARGUS_PATH"


#######################################
# Create .env if missing
#######################################
$envFile = Join-Path $ARGUS_PATH ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "Creating .env from example..."
    Copy-Item "$ARGUS_PATH\.env.example" $envFile
    Write-Host "Edit .env before first run."
}

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

#######################################
# Update VITE_API_URL
#######################################
$envText = Get-Content $envFile

if (-not $env:VITE_API_URL -or $FORCE_UPDATE_IP) {
    Write-Host "Setting VITE_API_URL=$COMPUTED_VITE_API_URL"

    if ($envText -match "^VITE_API_URL=") {
        $envText = $envText -replace "^VITE_API_URL=.*", "VITE_API_URL=$COMPUTED_VITE_API_URL"
    } else {
        $envText += "VITE_API_URL=$COMPUTED_VITE_API_URL"
    }

    Set-Content $envFile $envText
    $env:VITE_API_URL = $COMPUTED_VITE_API_URL
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
# # WebODM (optional)
# #######################################
# $ENABLE_WEBODM = $env:ENABLE_WEBODM -eq "true"
# $WEBODM_PATH = $env:WEBODM_PATH
# if (-not $WEBODM_PATH) {
#     $WEBODM_PATH = "$HOME\WebODM"
# }

# $WEBODM_URL = "http://$LOCAL_IP`:8000"
# $WEBODM_STARTED = $false

# if ($ENABLE_WEBODM -and (Test-Path "$WEBODM_PATH\webodm.sh")) {
#     Write-Host "Starting WebODM..."

#     Push-Location $WEBODM_PATH
#     & bash ./webodm.sh start
#     Pop-Location

#     $WEBODM_STARTED = $true
# }

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
