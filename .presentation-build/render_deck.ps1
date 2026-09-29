param([string]$Deck, [string]$OutDir, [string]$Pdf = "")
New-Item -ItemType Directory -Force $OutDir | Out-Null
$app = New-Object -ComObject PowerPoint.Application
$pres = $app.Presentations.Open($Deck, $true, $false, $false)
for ($i = 1; $i -le $pres.Slides.Count; $i++) {
    $pres.Slides.Item($i).Export((Join-Path $OutDir ("slide-{0:D2}.png" -f $i)), "PNG", 1600, 900)
}
if ($Pdf) { $pres.SaveAs($Pdf, 32) }
$pres.Close()
$app.Quit()
