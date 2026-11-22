param(
    [ValidateSet('build','reconfigure','size','size-components')]
    [string]$Action = 'build',
    [string]$BuildDirectory = 'build-waveshare7'
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
Push-Location $repo
try {
    $localIdf = Join-Path $repo '.cache/esp-idf-v5.5.2'
    $localTools = Join-Path $repo '.cache/espressif'
    $localPython = Join-Path $localTools 'python_env/idf5.5_py3.12_env/Scripts/python.exe'
    if (Test-Path -LiteralPath $localPython) {
        $env:IDF_PATH = $localIdf
        $env:IDF_TOOLS_PATH = $localTools
        $env:IDF_PYTHON_ENV_PATH = Split-Path (Split-Path $localPython -Parent) -Parent
        $env:PATH = "$(Split-Path $localPython -Parent);$env:PATH"
        . (Join-Path $localIdf 'export.ps1')
    } elseif (!$env:IDF_PATH) {
        throw 'Activate ESP-IDF 5.5.x first, or follow docs/BUILD_WINDOWS.md for the project-local environment.'
    }
    $idfPython = if (Test-Path -LiteralPath $localPython) { $localPython } else { (Get-Command python).Source }
    # Keep all optional cache writes in this checkout. The machine's inherited
    # ccache hung during the initial build, so use the compiler directly.
    $env:IDF_CCACHE_ENABLE = '0'
    $env:CCACHE_DIR = Join-Path $repo '.cache/ccache'
    & $idfPython (Join-Path $env:IDF_PATH 'tools/idf.py') --version
    if ($LASTEXITCODE -ne 0) { throw 'ESP-IDF environment check failed' }
    if (!(Test-Path -LiteralPath 'assets-8mb/manifest.txt')) { throw 'Run python tools/prepare_assets.py first (requires Pillow).' }
    # The allow-list above intentionally excludes flash, erase, monitor and
    # partition-flash commands. This helper cannot write to the ESP32.
    & $idfPython (Join-Path $env:IDF_PATH 'tools/idf.py') -B $BuildDirectory `
        -D 'CCACHE_ENABLE=OFF' `
        -D "SDKCONFIG=$BuildDirectory/sdkconfig" `
        -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.board.8mb;sdkconfig.board.waveshare7-8mb' $Action
    if ($LASTEXITCODE -ne 0) { throw "ESP-IDF $Action failed: $LASTEXITCODE" }
    if ($Action -eq 'build') {
        & $idfPython tools/validate_firmware.py --build-dir $BuildDirectory `
            --json-out "$BuildDirectory/validation.json"
        if ($LASTEXITCODE -ne 0) { throw 'Offline firmware safety validation failed' }
    }
} finally {
    Pop-Location
}
