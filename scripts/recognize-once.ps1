$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

try {
    Add-Type -AssemblyName System.Speech
}
catch {
    [Console]::Error.WriteLine("SYSTEM_SPEECH_UNAVAILABLE")
    exit 4
}

$installed = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()
if ($null -eq $installed -or $installed.Count -eq 0) {
    [Console]::Error.WriteLine("NO_RECOGNIZER")
    exit 3
}

$recognizerInfo = $null
foreach ($info in $installed) {
    if ($info.Culture.Name -in @("zh-CN", "zh-Hans", "zh")) {
        $recognizerInfo = $info
        break
    }
}

if ($null -eq $recognizerInfo) {
    $recognizerInfo = $installed[0]
}

$recognizer = $null
try {
    try {
        $recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine($recognizerInfo)
    }
    catch {
        $recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine
    }
    $grammar = New-Object System.Speech.Recognition.DictationGrammar
    $recognizer.LoadGrammar($grammar)
    $recognizer.SetInputToDefaultAudioDevice()

    $result = $recognizer.Recognize([TimeSpan]::FromSeconds(10))
    if ($null -eq $result -or [string]::IsNullOrWhiteSpace($result.Text)) {
        [Console]::Error.WriteLine("NO_SPEECH")
        exit 2
    }

    Write-Output $result.Text
}
catch {
    [Console]::Error.WriteLine("RECOGNITION_FAILED: $($_.Exception.Message)")
    exit 1
}
finally {
    if ($null -ne $recognizer) {
        $recognizer.Dispose()
    }
}
