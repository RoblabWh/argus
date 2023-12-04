# PowerShell Script

# Get path to argus
$ARGUS_PATH = (Get-Item -Path ".\" -Verbose).FullName
Write-Host "Installation path is $ARGUS_PATH"

# Set default environment variables
$env:ARGUS_PROJECTS = "projects"
$env:ARGUS_DB = "db"
$env:ARGUS_MEDIA = "media"
$env:ARGUS_PORT = "5000"
$env:ARGUS_WEBODM_PORT = "4000"

# Define Docker Compose command
$dockerComposeFile = "$ARGUS_PATH\docker-compose.yml"
$dockerCommand = "docker"
$dockerArgs = "compose", "-f", $dockerComposeFile, "up"

# Always use CPU
Write-Host "Using CPU"

# Run Docker Compose with provided arguments
$fullCommand = $dockerArgs + $args
Write-Host "Running command: $dockerCommand $fullCommand"
& $dockerCommand $fullCommand
