# 把雨课堂题目切图拼成可读长图（Windows / System.Drawing，无需安装依赖）
#
# 用法:
#   & .\compose_windows.ps1 -SrcDir "C:\path\imgs" -OutDir "C:\path\composed" -Scale 1.6 -PerGroup 2
#
# 输入文件名约定 q01_k1.png ... q01_k5.png（k1 为题干切图，k2~k5 为 A~D 选项）。
# 布局使用占位比例，容器尺寸变化时只改 -ItemW / -ItemH。

param(
    [Parameter(Mandatory = $true)][string]$SrcDir,
    [Parameter(Mandatory = $true)][string]$OutDir,
    [double]$Scale = 1.6,
    [int]$PerGroup = 2,
    [double]$ItemW = 360,
    [double]$ItemH = 600
)

Add-Type -AssemblyName System.Drawing

if (-not (Test-Path -LiteralPath $SrcDir)) { throw "SrcDir not found: $SrcDir" }
if (-not (Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

# 相对 .problem_item 的比例
$Stem = @{ x = 0.10; y = 0.06944; w = 0.80; h = 0.3125 }
$OptY = @(0.40625, 0.53125, 0.65625, 0.78125)
$Opt = @{ x = 0.20; w = 0.70; h = 0.09375 }
$BulletX = 0.09444
$BulletY = @(0.42312, 0.54812, 0.67312, 0.79812)
$Labels = @("A", "B", "C", "D")

$IW = [int]($ItemW * $Scale)
$IH = [int]($ItemH * $Scale)

$numbers = @()
Get-ChildItem -LiteralPath $SrcDir -Filter "q*_k*.png" | ForEach-Object {
    if ($_.Name -match '^q(\d+)_k(\d+)\.png$') { $numbers += [int]$matches[1] }
}
$numbers = $numbers | Sort-Object -Unique
if ($numbers.Count -eq 0) { throw "no qNN_kK.png found in $SrcDir" }

$font = New-Object System.Drawing.Font("Arial", [math]::Max(14, [int](18 * $Scale)), [System.Drawing.FontStyle]::Bold)
$fontBullet = New-Object System.Drawing.Font("Arial", [math]::Max(14, [int](18 * $Scale)), [System.Drawing.FontStyle]::Bold)
$brushBlack = [System.Drawing.Brushes]::Black
$brushGray = [System.Drawing.Brushes]::Gray

for ($start = 0; $start -lt $numbers.Count; $start += $PerGroup) {
    $group = @()
    for ($i = 0; $i -lt $PerGroup; $i++) {
        if (($start + $i) -lt $numbers.Count) { $group += $numbers[$start + $i] }
    }
    $bmp = New-Object System.Drawing.Bitmap($IW, ($IH * $group.Count))
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.Clear([System.Drawing.Color]::White)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

    $row = 0
    foreach ($q in $group) {
        $oy = $row * $IH
        $g.DrawString("No.$q", $font, $brushBlack, 6, ($oy + 4))

        $stemPath = Join-Path $SrcDir ("q{0:00}_k1.png" -f $q)
        if (Test-Path -LiteralPath $stemPath) {
            $img = [System.Drawing.Image]::FromFile($stemPath)
            $g.DrawImage($img, [int]($Stem.x * $IW), ($oy + [int]($Stem.y * $IH)), [int]($Stem.w * $IW), [int]($Stem.h * $IH))
            $img.Dispose()
        }

        for ($j = 0; $j -lt 4; $j++) {
            $optPath = Join-Path $SrcDir ("q{0:00}_k{1}.png" -f $q, ($j + 2))
            if (Test-Path -LiteralPath $optPath) {
                $img = [System.Drawing.Image]::FromFile($optPath)
                $g.DrawImage($img, [int]($Opt.x * $IW), ($oy + [int]($OptY[$j] * $IH)), [int]($Opt.w * $IW), [int]($Opt.h * $IH))
                $img.Dispose()
            }
            $g.DrawString($Labels[$j], $fontBullet, $brushGray, [int]($BulletX * $IW), ($oy + [int]($BulletY[$j] * $IH)))
        }
        $row++
    }

    $g.Dispose()
    $outPath = Join-Path $OutDir ("grp_{0:00}.png" -f $group[0])
    $bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

$font.Dispose(); $fontBullet.Dispose()
Write-Output ("composed: " + (Get-ChildItem -LiteralPath $OutDir -Filter *.png | Measure-Object).Count)
