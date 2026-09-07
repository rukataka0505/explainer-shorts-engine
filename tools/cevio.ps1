param(
    [Parameter(Mandatory = $true)]
    [string]$RequestPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding -ArgumentList $false
$OutputEncoding = [Console]::OutputEncoding

function Emit($value) {
    $value | ConvertTo-Json -Depth 8 -Compress
}

try {
    $request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $dll = $env:CEVIO_REMOTE_SERVICE_DLL
    if ($dll) {
        if (-not (Test-Path -LiteralPath $dll -PathType Leaf)) {
            throw "CEVIO_REMOTE_SERVICE_DLL was not found: $dll"
        }
        Add-Type -Path $dll
    }
    else {
        try {
            Add-Type -AssemblyName 'CeVIO.Talk.RemoteService2'
        }
        catch {
            throw 'CeVIO AI Talk Extension API was not found. Install and activate CeVIO AI Talk. If needed, set CEVIO_REMOTE_SERVICE_DLL to CeVIO.Talk.RemoteService2.dll.'
        }
    }

    $started = [CeVIO.Talk.RemoteService2.ServiceControl2]::StartHost($false)
    if ([int]$started -ne 0) {
        throw "CeVIO AI could not be started: $started"
    }
    $casts = @([CeVIO.Talk.RemoteService2.Talker2]::AvailableCasts)
    if ($request.action -eq 'check') {
        Emit ([ordered]@{ status = 'succeeded'; host_version = [CeVIO.Talk.RemoteService2.ServiceControl2]::HostVersion; casts = $casts })
        exit 0
    }
    if ($request.action -ne 'synthesize') {
        throw "Unsupported CeVIO action: $($request.action)"
    }

    $cast = [string]$request.cast
    if ($casts -notcontains $cast) {
        throw "CeVIO AI cast is not installed: $cast"
    }
    $talker = New-Object CeVIO.Talk.RemoteService2.Talker2
    $talker.Cast = $cast

    $scalar = @('Volume', 'Speed', 'Tone', 'Alpha', 'ToneScale')
    if ($null -ne $request.settings) {
        foreach ($property in $request.settings.PSObject.Properties) {
            if ($property.Name -eq 'Components') {
                foreach ($component in $property.Value.PSObject.Properties) {
                    $target = $talker.Components[$component.Name]
                    if ($null -eq $target) {
                        throw "Unsupported CeVIO component: $($component.Name)"
                    }
                    $value = [int]$component.Value
                    if ($value -lt 0 -or $value -gt 100) {
                        throw "CeVIO settings must be between 0 and 100: Components.$($component.Name)"
                    }
                    $target.Value = [uint32]$value
                }
                continue
            }
            if ($scalar -notcontains $property.Name) {
                throw "Unsupported CeVIO setting: $($property.Name)"
            }
            $value = [int]$property.Value
            if ($value -lt 0 -or $value -gt 100) {
                throw "CeVIO settings must be between 0 and 100: $($property.Name)"
            }
            $talker.($property.Name) = [uint32]$value
        }
    }

    $output = [IO.Path]::GetFullPath([string]$request.output)
    $parent = [IO.Path]::GetDirectoryName($output)
    if ($parent) {
        [IO.Directory]::CreateDirectory($parent) | Out-Null
    }
    if (-not $talker.OutputWaveToFile([string]$request.text, $output)) {
        throw 'CeVIO AI failed to output WAV.'
    }
    Emit ([ordered]@{ status = 'succeeded'; host_version = [CeVIO.Talk.RemoteService2.ServiceControl2]::HostVersion; cast = $cast })
}
catch {
    Emit ([ordered]@{ status = 'failed'; error = $_.Exception.Message })
    exit 1
}
