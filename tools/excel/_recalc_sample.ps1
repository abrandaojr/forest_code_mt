param([int]$Part)
$p = (Resolve-Path ('outputs\codigo_florestal_mt_completo_formulas_parte_{0:D2}.xlsx' -f $Part)).Path
$out = Join-Path (Get-Location) 'outputs\_formula_recalc_sample.tsv'
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$wb = $excel.Workbooks.Open($p)
$excel.CalculateFullRebuild()
$ws = $wb.Worksheets.Item(1)
$arr = $ws.Range('A1:EA101').Value2
$sw = [IO.StreamWriter]::new($out, $false, [Text.UTF8Encoding]::new($false))
for ($j = 1; $j -le 123; $j++) {
    $f = $ws.Cells.Item(2, $j).Formula
    if ($f -is [string] -and $f.StartsWith('=')) {
        for ($i = 2; $i -le 101; $i++) {
            $v = $arr[$i, $j]
            $sw.WriteLine("$($i-2)`t$($arr[1,$j])`t$v")
        }
    }
}
$sw.Close()
$wb.Close($false)
$excel.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
