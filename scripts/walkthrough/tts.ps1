# Narration clips with the built-in Windows (OneCore) speech voices: one WAV per chapter.
# Usage: powershell -File tts.ps1 -Narration narration.json -OutDir <dir> [-Voice "Microsoft Mark"]
param(
    [Parameter(Mandatory)] [string] $Narration,
    [Parameter(Mandatory)] [string] $OutDir,
    [string] $Voice = "Microsoft Mark",
    [double] $Rate = 1.0
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null

$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq "AsTask" -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
function Await($op, [Type] $type) {
    $task = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
    $task.Wait() | Out-Null
    $task.Result
}

$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$synth.Voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.DisplayName -eq $Voice } | Select-Object -First 1
$synth.Options.SpeakingRate = $Rate
New-Item -ItemType Directory -Force $OutDir | Out-Null

$segments = Get-Content -Raw -Encoding UTF8 $Narration | ConvertFrom-Json
foreach ($s in $segments) {
    $stream = Await ($synth.SynthesizeTextToStreamAsync($s.text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
    $reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
    $size = [uint32] $stream.Size
    Await ($reader.LoadAsync($size)) ([uint32]) | Out-Null
    $bytes = New-Object byte[] $size
    $reader.ReadBytes($bytes)
    [System.IO.File]::WriteAllBytes((Join-Path $OutDir "$($s.id).wav"), $bytes)
    Write-Output "$($s.id) $size"
}
