# Nájde priečinok hry Black Mirror v Steame (hlavná knižnica aj ďalšie knižnice z libraryfolders.vdf).
# Vypíše cestu k priečinku s agds.exe, inak nič. Používajú ho install.bat a uninstall.bat.
$kniznice = @()
foreach ($kluc in 'HKCU:\Software\Valve\Steam', 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam', 'HKLM:\SOFTWARE\Valve\Steam') {
    $p = Get-ItemProperty -Path $kluc -ErrorAction SilentlyContinue
    if ($p.SteamPath) { $kniznice += $p.SteamPath }
    if ($p.InstallPath) { $kniznice += $p.InstallPath }
}
foreach ($steam in @($kniznice)) {
    $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
    if (Test-Path $vdf) {
        foreach ($m in (Select-String -Path $vdf -Pattern '"path"\s+"([^"]+)"')) {
            $kniznice += ($m.Matches[0].Groups[1].Value -replace '\\\\', '\')
        }
    }
}
foreach ($k in $kniznice) {
    $hra = Join-Path $k 'steamapps\common\Black Mirror'
    if (Test-Path (Join-Path $hra 'agds.exe')) { (Resolve-Path $hra).Path; exit 0 }
}
exit 1
