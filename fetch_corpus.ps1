# Pull raw HTML for every known gsmg.io puzzle page into corpus/.
# Raw, not rendered: hidden inputs, HTML comments and script blocks are exactly
# where this puzzle has hidden things before.
#
# Every page first serves a FingerprintJS shim that redirects to itself with
# ?tr_uuid=...&fp=<id>. The shim ships its own no-JS fallback link; we follow
# that rather than executing anything.
#
# gsmg.io drops connections if you burst it, so requests are spaced and share
# one cookie session. Do not lower $Delay.

param([int]$Cooldown = 60, [double]$Delay = 6)

$ProgressPreference = 'SilentlyContinue'
$dir = Join-Path $PSScriptRoot 'corpus'
New-Item -ItemType Directory -Force $dir | Out-Null

$UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$session.UserAgent = $UA

$urls = [ordered]@{
  'root'               = 'https://gsmg.io/'
  'puzzle'             = 'https://gsmg.io/puzzle'
  'theseedisplanted'   = 'https://gsmg.io/theseedisplanted'
  'choiceisanillusion' = 'https://gsmg.io/choiceisanillusioncreatedbetweenthosewithpowerandthosewithoutaveryspecialdessertiwroteitmyself'
  'salphaseion'        = 'https://gsmg.io/89727c598b9cd1cf8873f27cb7057f050645ddb6a7a157a110239ac0152f6a32'
  'causality_hash'     = 'https://gsmg.io/eb3efb5151e6255994711fe8f2264427ceeebf88109e1d7fad5b0a8b6d07e5bf'
  'phase3_hash'        = 'https://gsmg.io/1a57c572caf3cf722e41f5f9cf99ffacff06728a43032dd44c481c77d2ec30d5'
  'phase32_hash'       = 'https://gsmg.io/250f37726d6862939f723edc4f993fde9d33c6004aab4f2203d9ee489d61ce4c'
}

function Get-Raw([string]$url) {
  Start-Sleep -Seconds $Delay
  Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 40 -WebSession $session
}

if ($Cooldown -gt 0) {
  "cooling down $Cooldown s before touching gsmg.io again..."
  Start-Sleep -Seconds $Cooldown
}

foreach ($k in $urls.Keys) {
  $out = Join-Path $dir "$k.html"
  try {
    $r = Get-Raw $urls[$k]
    # Shim's hidden anchor carries the fp=-3 no-JS variant. It is advertised as
    # http://; port 80 does not answer, so upgrade the scheme.
    $m = [regex]::Match($r.Content, "href='(http[^']*fp=-3)'")
    if ($m.Success) {
      $r = Get-Raw ($m.Groups[1].Value -replace '^http://', 'https://')
    }
    [IO.File]::WriteAllText($out, $r.Content, [Text.UTF8Encoding]::new($false))
    $shim = if ($r.Content -match 'FingerprintJS') { 'SHIM' } else { 'content' }
    "{0,-22} {1}  {2,7} bytes  {3}" -f $k, $r.StatusCode, $r.Content.Length, $shim
  } catch {
    "{0,-22} FAIL {1}" -f $k, $_.Exception.Message.Split("`n")[0]
  }
}
