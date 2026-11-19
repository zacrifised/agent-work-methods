# Windows.Media.Ocr (built into Windows) - a second, architecturally different engine.
param([string]$Path, [string]$Out)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
  Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
                 $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($WinRtTask, $ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($WinRtTask))
  $netTask.Wait(-1) | Out-Null
  $netTask.Result
}
[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null

Write-Host "available languages:"
[Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages | ForEach-Object { Write-Host ("  " + $_.LanguageTag + "  " + $_.DisplayName) }

$file    = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
$stream  = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap  = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

$engine = $null
foreach ($tag in @('zh-Hans-CN','zh-Hans','zh-CN')) {
  try {
    $lang = New-Object Windows.Globalization.Language($tag)
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
    if ($engine) { Write-Host ("engine language: " + $tag); break }
  } catch {}
}
if (-not $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if (-not $engine) { Write-Host "NO OCR ENGINE"; exit 1 }

$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$lines = @()
foreach ($ln in $result.Lines) {
  $ws = @()
  foreach ($w in $ln.Words) {
    $r = $w.BoundingRect
    $ws += [pscustomobject]@{ t = $w.Text; x = [int]$r.X; y = [int]$r.Y; w = [int]$r.Width; h = [int]$r.Height }
  }
  $lines += [pscustomobject]@{ text = $ln.Text; words = $ws }
}
$lines | ConvertTo-Json -Depth 5 | Out-File -Encoding utf8 $Out
Write-Host ("lines: " + $lines.Count)
