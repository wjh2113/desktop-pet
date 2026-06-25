$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -AssemblyName System.Speech

$recognizerInfo = $null
$installed = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()

foreach ($info in $installed) {
    if ($info.Culture.Name -eq "zh-CN" -or $info.Culture.Name -eq "zh-Hans") {
        $recognizerInfo = $info
        break
    }
}

if ($null -eq $recognizerInfo -and $installed.Count -gt 0) {
    $recognizerInfo = $installed[0]
}

if ($null -eq $recognizerInfo) {
    Write-Error "没有找到可用的 Windows 语音识别器。"
    exit 3
}

$recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine($recognizerInfo)
$grammar = New-Object System.Speech.Recognition.DictationGrammar
$recognizer.LoadGrammar($grammar)
$recognizer.SetInputToDefaultAudioDevice()

try {
    $result = $recognizer.Recognize([TimeSpan]::FromSeconds(7))
    if ($null -eq $result -or [string]::IsNullOrWhiteSpace($result.Text)) {
        Write-Error "没有听清楚。"
        exit 2
    }
    Write-Output $result.Text
}
finally {
    $recognizer.Dispose()
}
