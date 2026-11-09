<#
.SYNOPSIS
  Tablet sem Obsolescência — kit de varredura e limpeza via ADB (sem root), versão PowerShell.

.DESCRIPTION
  Mesmos comandos da versão Python, lendo o mesmo banco (dados\pacotes.json) e gravando
  os mesmos registros (relatorios\...), então dá para alternar entre as duas.
  Funciona no Windows PowerShell 5.1 e no PowerShell 7.

.EXAMPLE
  .\TabletKit.ps1 verificar
  .\TabletKit.ps1 varrer
  .\TabletKit.ps1 medir -Rotulo antes
  .\TabletKit.ps1 remover                       # simulação
  .\TabletKit.ps1 remover -Aplicar              # executa (pede confirmação)
  .\TabletKit.ps1 remover -Risco cuidado -Categoria limitador -Aplicar
  .\TabletKit.ps1 remover -Pacote com.facebook.appmanager -Aplicar
  .\TabletKit.ps1 reverter -Tudo
  .\TabletKit.ps1 otimizar -Aplicar
  .\TabletKit.ps1 restaurar-otimizacoes
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet('verificar', 'varrer', 'medir', 'remover', 'reverter', 'otimizar', 'restaurar-otimizacoes', 'reiniciar')]
    [string]$Acao,
    [string]$Serial,
    [ValidateSet('seguro', 'cuidado')][string]$Risco = 'seguro',
    [string[]]$Categoria,
    [string[]]$Pacote,
    [ValidateSet('desinstalar', 'desativar')][string]$Modo = 'desinstalar',
    [ValidateSet('0', '0.5', '1')][string]$Animacao = '0.5',
    [string]$Rotulo = '',
    [switch]$Aplicar,
    [switch]$Sim,
    [switch]$Tudo,
    [switch]$SemCompilar
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$Raiz = Split-Path -Parent $PSScriptRoot
$BancoArq = Join-Path $Raiz 'dados\pacotes.json'
$PastaRelatorios = Join-Path $Raiz 'relatorios'
$NivelRisco = @{ seguro = 0; cuidado = 1; perigoso = 2 }
$SaudeBateria = @{ '1' = 'desconhecida'; '2' = 'boa'; '3' = 'superaquecida'; '4' = 'morta'; '5' = 'sobretensão'; '6' = 'falha'; '7' = 'fria' }

# ----------------------------------------------------------------- ADB
function Find-Adb {
    $cands = @($env:TABLETKIT_ADB, (Get-Command adb -ErrorAction SilentlyContinue | ForEach-Object Source),
        (Join-Path $Raiz 'platform-tools\adb.exe'))
    foreach ($c in $cands) { if ($c -and (Test-Path $c)) { return $c } }
    throw "ADB não encontrado. Rode: powershell -ExecutionPolicy Bypass -File scripts\instalar-adb.ps1  (ou defina TABLETKIT_ADB)"
}
$Adb = $null

function Invoke-Adb([string[]]$Argumentos) {
    $base = @(); if ($script:Serial) { $base = @('-s', $script:Serial) }
    $saida = & $Adb @($base + $Argumentos) 2>&1 | ForEach-Object { "$_" }
    return ($saida -join "`n")
}
function Invoke-Shell([string]$Comando) { (Invoke-Adb @('shell', $Comando)).Trim() }
function Get-Prop([string]$Nome) { Invoke-Shell "getprop $Nome" }
function Get-Pacotes([string]$Flag = '') {
    $s = Invoke-Shell ("pm list packages $Flag").Trim()
    $set = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($l in $s -split "`n") { if ($l -like 'package:*') { [void]$set.Add($l.Substring(8).Trim()) } }
    return , $set
}

function Select-Aparelho {
    if ($script:Serial) { return }
    $linhas = (Invoke-Adb @('devices')) -split "`n" | Select-Object -Skip 1
    $prontos = @(); $nao = @()
    foreach ($l in $linhas) {
        $p = $l.Trim() -split '\s+'
        if ($p.Count -ge 2) { if ($p[1] -eq 'device') { $prontos += $p[0] } else { $nao += $p[1] } }
    }
    if ($prontos.Count -eq 0) {
        $msg = "Nenhum tablet conectado."
        if ($nao -contains 'unauthorized') { $msg += " Desbloqueie o tablet e aceite 'Permitir depuração USB'." }
        throw "$msg Confira Depuração USB ligada e cabo de dados."
    }
    if ($prontos.Count -gt 1) { throw "Mais de um aparelho conectado ($($prontos -join ', ')). Use -Serial." }
    $script:Serial = $prontos[0]
}

# ----------------------------------------------------------------- banco
$Banco = Get-Content $BancoArq -Raw -Encoding UTF8 | ConvertFrom-Json
$PorPacote = @{}; foreach ($p in $Banco.pacotes) { $PorPacote[$p.pacote] = $p }
$PadroesOcultos = @(); if ($Banco.padroes_ocultos) { $PadroesOcultos = @($Banco.padroes_ocultos.contem) }
$Componentes = @{}; $MotivoComponente = 'Componente do sistema.'
if ($Banco.componentes_sistema) {
    foreach ($c in $Banco.componentes_sistema.pacotes) { $Componentes[$c] = $true }
    $MotivoComponente = $Banco.componentes_sistema.motivo
}

# Overlays/recursos não catalogados: não rodam nem gastam RAM, ficam fora do relatório.
function Test-Oculto([string]$Nome) {
    if ($PorPacote.ContainsKey($Nome)) { return $false }
    foreach ($s in $script:PadroesOcultos) { if ($Nome.Contains($s)) { return $true } }
    return $false
}

function Get-Classificacao([string]$Nome) {
    if ($PorPacote.ContainsKey($Nome)) { return $PorPacote[$Nome] }
    if ($script:Componentes.ContainsKey($Nome)) { return [pscustomobject]@{ pacote = $Nome; nome = $Nome; categoria = 'essencial'; risco = 'perigoso'; motivo = $script:MotivoComponente } }
    foreach ($pre in $Banco.prefixos_perigosos) {
        if ($Nome.StartsWith($pre)) { return [pscustomobject]@{ pacote = $Nome; nome = $Nome; categoria = 'essencial'; risco = 'perigoso'; motivo = 'Componente do sistema (por prefixo).' } }
    }
    foreach ($s in $Banco.padroes_suspeitos) {
        if ($Nome.StartsWith($s.prefixo)) { return [pscustomobject]@{ pacote = $Nome; nome = $Nome; categoria = 'suspeito'; risco = 'verificar'; motivo = $s.motivo } }
    }
    return [pscustomobject]@{ pacote = $Nome; nome = $Nome; categoria = 'nao_catalogado'; risco = 'verificar'; motivo = 'Não está no banco. Pesquise antes de remover.' }
}

# ----------------------------------------------------------------- registros
function Get-PastaAparelho {
    $modelo = (Get-Prop 'ro.product.model') -replace '[^A-Za-z0-9_-]', '_'
    if (-not $modelo) { $modelo = 'tablet' }
    $p = Join-Path $PastaRelatorios ("{0}_{1}" -f $modelo, ($script:Serial -replace '[^A-Za-z0-9_-]', '_'))
    New-Item -ItemType Directory -Force $p | Out-Null
    return $p
}
function Agora { (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss') }
function Add-Registro([string]$Pasta, [string]$Arquivo, [hashtable]$Dados) {
    $obj = [ordered]@{ data = (Agora) }; foreach ($k in $Dados.Keys) { $obj[$k] = $Dados[$k] }
    $linha = ($obj | ConvertTo-Json -Compress -Depth 5)
    [System.IO.File]::AppendAllText((Join-Path $Pasta $Arquivo), $linha + "`n", (New-Object System.Text.UTF8Encoding $false))
}
function Get-Registros([string]$Pasta, [string]$Arquivo) {
    $c = Join-Path $Pasta $Arquivo
    if (-not (Test-Path $c)) { return @() }
    return @(Get-Content $c -Encoding UTF8 | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
}
function Save-BackupPacotes([string]$Pasta) {
    $dest = Join-Path $Pasta ("pacotes-ativos-{0}.txt" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    $lista = @(Get-Pacotes '-e') | Sort-Object
    [System.IO.File]::WriteAllText($dest, ($lista -join "`n") + "`n", (New-Object System.Text.UTF8Encoding $false))
    return $dest
}
function Confirm-Acao([string]$Pergunta) {
    if ($Sim) { return $true }
    $r = Read-Host "$Pergunta Digite SIM para continuar"
    return ($r.Trim().ToUpper() -eq 'SIM')
}
function Format-GB([double]$Kb) { '{0:N2} GB' -f ($Kb / 1MB) }

# ----------------------------------------------------------------- coleta
function Get-InfoAparelho {
    $props = [ordered]@{ fabricante = 'ro.product.manufacturer'; modelo = 'ro.product.model'; codinome = 'ro.product.device';
        android = 'ro.build.version.release'; sdk = 'ro.build.version.sdk'; patch_seguranca = 'ro.build.version.security_patch';
        abi = 'ro.product.cpu.abi'; plataforma = 'ro.board.platform'; build = 'ro.build.display.id' }
    $i = [ordered]@{}; foreach ($k in $props.Keys) { $i[$k] = Get-Prop $props[$k] }
    $i['serial'] = $script:Serial
    return $i
}
function Get-Memoria {
    $v = @{}
    foreach ($l in (Invoke-Shell 'cat /proc/meminfo') -split "`n") { if ($l -match '^(\w+):\s+(\d+)') { $v[$Matches[1]] = [long]$Matches[2] } }
    [ordered]@{ total_kb = $v['MemTotal']; disponivel_kb = $v['MemAvailable']; swap_total_kb = $v['SwapTotal']; swap_livre_kb = $v['SwapFree'] }
}
function Get-Armazenamento {
    foreach ($l in ((Invoke-Shell 'df -k /data') -split "`n" | Select-Object -Skip 1)) {
        $p = $l.Trim() -split '\s+'
        if ($p.Count -ge 4 -and $p[1] -match '^\d+$') {
            $t = [long]$p[1]; $u = [long]$p[2]
            return [ordered]@{ total_kb = $t; usado_kb = $u; livre_kb = [long]$p[3]; uso_pct = [math]::Round($u * 100 / [math]::Max($t, 1), 1) }
        }
    }
    return [ordered]@{ uso_pct = 0 }
}
function Get-Bateria {
    $b = @{}
    foreach ($l in (Invoke-Shell 'dumpsys battery') -split "`n") { if ($l -match '^\s*([^:]+):\s*(.*)$') { $b[$Matches[1].Trim()] = $Matches[2].Trim() } }
    $temp = $null; if ($b['temperature'] -match '^-?\d+$') { $temp = [math]::Round([int]$b['temperature'] / 10, 1) }
    $saude = $b['health']; if ($SaudeBateria.ContainsKey("$saude")) { $saude = $SaudeBateria["$saude"] }
    [ordered]@{ nivel_pct = $b['level']; saude = $saude; temperatura_c = $temp; tensao_mv = $b['voltage'] }
}
function Get-Animacoes {
    $r = [ordered]@{}
    foreach ($c in 'window_animation_scale', 'transition_animation_scale', 'animator_duration_scale') { $r[$c] = Invoke-Shell "settings get global $c" }
    return $r
}
function Get-AppsBoot {
    $s = Invoke-Shell 'cmd package query-receivers --brief -a android.intent.action.BOOT_COMPLETED'
    @($s -split "`n" | Where-Object { $_ -match '/' -and $_ -notmatch '^(Error|Exception)' } | ForEach-Object { ($_.Trim() -split '/')[0] } | Sort-Object -Unique)
}
function Get-TopRam([int]$Limite = 15) {
    $res = @(); $dentro = $false
    foreach ($l in (Invoke-Shell 'dumpsys meminfo') -split "`n") {
        if ($l -match 'Total (PSS|RSS) by process') { if ($res.Count) { break }; $dentro = $true; continue }
        if ($dentro) {
            if ($l -match '^\s*([\d,]+)K: (\S+) \(pid') { $res += [pscustomobject]@{ pacote = $Matches[2]; ram_mb = [math]::Round(([long]($Matches[1] -replace ',', '')) / 1024, 1) } }
            elseif ($res.Count -and -not $l.Trim()) { break }
        }
        if ($res.Count -ge $Limite) { break }
    }
    return $res
}
function Measure-AberturaConfig([int]$Vezes = 3) {
    $t = @()
    for ($i = 0; $i -lt $Vezes; $i++) {
        Invoke-Shell 'am force-stop com.android.settings' | Out-Null
        $s = Invoke-Shell 'am start -W -n com.android.settings/.Settings'
        if ($s -match 'TotalTime:\s*(\d+)') { $t += [int]$Matches[1] }
    }
    Invoke-Shell 'input keyevent KEYCODE_HOME' | Out-Null
    if ($t.Count) { return [int][math]::Round(($t | Measure-Object -Average).Average) } else { return $null }
}

# ----------------------------------------------------------------- comandos
function Invoke-Verificar {
    $i = Get-InfoAparelho
    Write-Host "OK Conectado: $($i.fabricante) $($i.modelo) ($($i.codinome)) - Android $($i.android) (SDK $($i.sdk)), serial $Serial" -ForegroundColor Green
}

function Get-Alertas($d) {
    $out = @()
    $ativos = @(); foreach ($k in 'seguro', 'cuidado', 'perigoso', 'verificar') { $ativos += @($d.classificacao[$k] | ForEach-Object { $_.pacote }) }
    if ($ativos -contains 'com.samsung.android.game.gos') { $out += '- ⚠️ **Game Optimizing Service ativo:** limita o desempenho de jogos e apps pesados.' }
    if ($ativos -contains 'com.wssyncmldm' -or $ativos -contains 'com.sec.android.soagent') {
        $out += '- ℹ️ **Atualizações automáticas ativas.** Em tablets antigos, versões novas podem pesar mais. Bloquear atualizações também bloqueia correções de segurança: decida com cuidado.' }
    if ($d.armazenamento.uso_pct -gt 85) { $out += '- ⚠️ **Armazenamento quase cheio.** Acima de ~85% o sistema de arquivos fica lento.' }
    if ($d.bateria.saude -and @('boa', 'desconhecida') -notcontains $d.bateria.saude) {
        $out += "- ⚠️ **Bateria com saúde '$($d.bateria.saude)'.** Bateria gasta faz o sistema reduzir a CPU; trocar a bateria pode ser a melhor 'otimização'." }
    if ($d.bateria.temperatura_c -ge 40) { $out += '- ⚠️ **Tablet quente (≥ 40 °C).** O sistema reduz a velocidade para esfriar.' }
    $patch = "$($d.aparelho.patch_seguranca)"
    if ($patch.Length -ge 4 -and ((Get-Date).Year - [int]$patch.Substring(0, 4)) -ge 2) {
        $out += "- ℹ️ **Patch de segurança de $patch.** O fabricante parou de atualizar; cuidado com bancos e apps sensíveis." }
    $sujos = @($d.iniciam_no_boot | Where-Object { @('propaganda', 'telemetria') -contains $_.categoria })
    if ($sujos.Count) { $out += "- ⚠️ **$($sujos.Count) apps de propaganda/telemetria iniciam junto com o tablet.**" }
    return $out
}

function Invoke-Varrer {
    $pasta = Get-PastaAparelho
    Write-Host 'Varrendo o tablet... (pode levar 1 a 2 minutos)'
    $info = Get-InfoAparelho
    $ativos = Get-Pacotes '-e'; $desat = Get-Pacotes '-d'; $sistema = Get-Pacotes '-s'
    $todosU = Get-Pacotes '-u'; $inst = Get-Pacotes ''
    $removidos = @($todosU | Where-Object { -not $inst.Contains($_) } | Sort-Object)

    $cls = [ordered]@{ seguro = @(); cuidado = @(); perigoso = @(); verificar = @() }
    $qtdOcultos = 0
    foreach ($p in ($ativos | Sort-Object)) {
        $c = Get-Classificacao $p
        $ehSistema = $sistema.Contains($p)
        if ($c.risco -eq 'verificar') {
            if (-not $ehSistema) { continue }                  # app de terceiro não catalogado
            if (Test-Oculto $p) { $qtdOcultos++; continue }    # overlay/recurso
        }
        $cls[$c.risco] += [pscustomobject]@{ pacote = $p; nome = $c.nome; categoria = $c.categoria; risco = $c.risco; motivo = $c.motivo; sistema = $ehSistema }
    }
    $boot = @(Get-AppsBoot | Where-Object { $ativos.Contains($_) } | ForEach-Object {
            $c = Get-Classificacao $_
            [pscustomobject]@{ pacote = $_; terceiro = (-not $sistema.Contains($_)); risco = $c.risco; categoria = $c.categoria } })
    $terceiros = @($ativos | Where-Object { -not $sistema.Contains($_) }).Count

    $d = [ordered]@{
        data = (Agora); aparelho = $info; memoria = (Get-Memoria); armazenamento = (Get-Armazenamento)
        bateria = (Get-Bateria); animacoes = (Get-Animacoes)
        contagem = [ordered]@{ ativos = $ativos.Count; desativados = $desat.Count; sistema = $sistema.Count; terceiros = $terceiros
            removidos_usuario0 = $removidos.Count; overlays_ocultos = $qtdOcultos }
        classificacao = $cls; iniciam_no_boot = $boot; maiores_consumidores_ram = @(Get-TopRam)
        ja_removidos = $removidos; desativados = @($desat | Sort-Object)
    }
    $carimbo = Get-Date -Format 'yyyyMMdd-HHmmss'
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText((Join-Path $pasta "varredura-$carimbo.json"), ($d | ConvertTo-Json -Depth 6), $utf8)

    $alertas = Get-Alertas $d
    $L = @("# Varredura — $($info.fabricante) $($info.modelo)", '', "Data: $($d.data)", '', '## Aparelho', '', '| Item | Valor |', '|---|---|')
    foreach ($k in $info.Keys) { if ($k -ne 'serial') { $L += "| $k | $($info[$k]) |" } }
    $m = $d.memoria; $s = $d.armazenamento; $b = $d.bateria
    $L += '', '## Saúde', '', "- **RAM:** $(Format-GB $m.disponivel_kb) livres de $(Format-GB $m.total_kb)",
    "- **Armazenamento:** $(Format-GB $s.livre_kb) livres ($($s.uso_pct)% usado)",
    "- **Bateria:** $($b.nivel_pct)%, saúde $($b.saude), $($b.temperatura_c) °C",
    "- **Animações:** $(($d.animacoes.Values) -join ' / ') (janela / transição / duração)",
    ("- **Pacotes:** {0} ativos ({1} do sistema, {2} de terceiros), {3} desativados, {4} já removidos, {5} overlays ocultos" -f `
        $d.contagem.ativos, $d.contagem.sistema, $d.contagem.terceiros, $d.contagem.desativados, $d.contagem.removidos_usuario0, $d.contagem.overlays_ocultos), ''
    if ($alertas) { $L += '## Alertas', ''; $L += $alertas }
    $rot = [ordered]@{ seguro = '✅ Pode remover'; cuidado = '⚠️ Remover com cuidado'; verificar = '🔎 Apps do sistema não catalogados (pesquise antes)'; perigoso = '⛔ Essenciais (o kit não remove)' }
    foreach ($k in $rot.Keys) {
        $L += '', "## $($rot[$k]) — $($cls[$k].Count)", ''
        if (-not $cls[$k].Count) { $L += '_nenhum_'; continue }
        $L += '| Pacote | Nome | Categoria | Motivo |', '|---|---|---|---|'
        foreach ($p in $cls[$k]) { $L += "| ``$($p.pacote)`` | $($p.nome) | $($p.categoria) | $($p.motivo) |" }
    }
    $bootTer = @($boot | Where-Object { $_.terceiro }); $bootSis = @($boot | Where-Object { -not $_.terceiro })
    $L += '', "## Apps de terceiros que iniciam sozinhos ao ligar — $($bootTer.Count)", '',
    'Instalados por você, pela loja ou pré-carregados pelo fabricante. Desinstale pela Play Store os que não usa.', ''
    if ($bootTer.Count) { $L += @($bootTer | ForEach-Object { if ($_.risco -ne 'verificar') { "- ``$($_.pacote)`` ($($_.risco))" } else { "- ``$($_.pacote)``" } }) } else { $L += '_nenhum_' }
    $L += '', "## Apps do sistema que iniciam sozinhos ao ligar — $($bootSis.Count)", ''
    if ($bootSis.Count) { $L += @($bootSis | ForEach-Object { "- ``$($_.pacote)`` ($($_.risco))" }) } else { $L += '_nenhum_' }
    $L += '', '## Maiores consumidores de RAM agora', ''
    if ($d.maiores_consumidores_ram.Count) { $L += @($d.maiores_consumidores_ram | ForEach-Object { "- ``$($_.pacote)`` — $($_.ram_mb) MB" }) } else { $L += '_não disponível_' }
    $L += '', '---', 'Próximo passo: `.\TabletKit.ps1 remover` (simulação) e depois `-Aplicar`.', ''
    $md = Join-Path $pasta "varredura-$carimbo.md"
    [System.IO.File]::WriteAllText($md, ($L -join "`n"), $utf8)
    Save-BackupPacotes $pasta | Out-Null

    Write-Host ""
    Write-Host "$($info.fabricante) $($info.modelo) - Android $($info.android) - RAM livre $(Format-GB $m.disponivel_kb) / $(Format-GB $m.total_kb)" -ForegroundColor Cyan
    Write-Host ("  removíveis: {0}   com cuidado: {1}   não catalogados: {2}   essenciais: {3}" -f $cls.seguro.Count, $cls.cuidado.Count, $cls.verificar.Count, $cls.perigoso.Count)
    foreach ($a in $alertas) { Write-Host ('  ' + ($a -replace '^- ', '' -replace '\*\*', '')) -ForegroundColor Yellow }
    Write-Host "`nRelatório completo: $md"
}

function Invoke-Medir {
    $pasta = Get-PastaAparelho
    Write-Host 'Medindo (abre as Configurações 3 vezes)...'
    $med = @{ ram_livre_kb = (Get-Memoria).disponivel_kb; apps_ativos = (Get-Pacotes '-e').Count; abrir_config_ms = (Measure-AberturaConfig); rotulo = $Rotulo }
    $ant = @(Get-Registros $pasta 'medicoes.jsonl')
    Add-Registro $pasta 'medicoes.jsonl' $med
    Write-Host "  RAM livre: $(Format-GB $med.ram_livre_kb) | apps ativos: $($med.apps_ativos) | Configurações abriram em $($med.abrir_config_ms) ms"
    $marcadasAntes = @($ant | Where-Object { $_.rotulo -eq 'antes' })
    if ($ant.Count -and $Rotulo -ne 'antes') {
        # compara com a última medição "antes"; se não houver, com a primeira registrada
        if ($marcadasAntes.Count) { $p = $marcadasAntes[-1]; $origem = "medição 'antes'" }
        else { $p = $ant[0]; $origem = "1ª medição (nenhuma marcada como 'antes')" }
        Write-Host "`nComparado com a $origem de $($p.data):"
        Write-Host "  RAM livre: $(Format-GB $p.ram_livre_kb) -> $(Format-GB $med.ram_livre_kb)"
        Write-Host "  Apps ativos: $($p.apps_ativos) -> $($med.apps_ativos)"
        if ($p.abrir_config_ms -and $med.abrir_config_ms) {
            $g = ($p.abrir_config_ms - $med.abrir_config_ms) / $p.abrir_config_ms * 100
            Write-Host ("  Abertura: {0} -> {1} ms ({2:+0;-0}% mais rápido)" -f $p.abrir_config_ms, $med.abrir_config_ms, $g)
        }
        Write-Host '  (Para comparar de forma justa, reinicie o tablet e espere 2 min antes de medir.)'
    }
}

function Invoke-Remover {
    $ativos = Get-Pacotes '-e'
    $alvo = @()
    if ($Pacote) {
        foreach ($p in $Pacote) {
            $c = Get-Classificacao $p
            if (-not $ativos.Contains($p)) { Write-Host "  -> ${p}: não está instalado/ativo, ignorado." }
            elseif ($c.risco -eq 'perigoso') { Write-Host "  BLOQUEADO ${p}: ESSENCIAL ($($c.motivo))" -ForegroundColor Red }
            else { if ($c.risco -eq 'verificar') { Write-Host "  ATENÇÃO ${p}: não catalogado. Você assume o risco." -ForegroundColor Yellow }; $alvo += $c }
        }
    } else {
        $lim = $NivelRisco[$Risco]
        foreach ($p in ($ativos | Sort-Object)) {
            $c = Get-Classificacao $p
            if ($NivelRisco.ContainsKey($c.risco) -and $NivelRisco[$c.risco] -le $lim -and $c.risco -ne 'perigoso') {
                if (-not $Categoria -or $Categoria -contains $c.categoria) { $alvo += $c }
            }
        }
    }
    if (-not $alvo.Count) { Write-Host 'Nada para remover com esses filtros.'; return }
    $acaoTxt = if ($Modo -eq 'desativar') { 'DESATIVAR' } else { 'REMOVER (usuário 0)' }
    Write-Host "`n$($alvo.Count) app(s) para ${acaoTxt}:"
    foreach ($p in $alvo) { Write-Host ("  [{0,8}] {1,-50} {2} - {3}" -f $p.risco, $p.pacote, $p.nome, $p.motivo) }
    if (-not $Aplicar) { Write-Host "`nSIMULAÇÃO: nada foi alterado. Rode de novo com -Aplicar para executar." -ForegroundColor Cyan; return }
    if (-not (Confirm-Acao "`nIsso vai $($acaoTxt.ToLower()) $($alvo.Count) app(s). É reversível com 'reverter'.")) { Write-Host 'Cancelado.'; return }

    $pasta = Get-PastaAparelho
    Write-Host "Backup da lista de apps: $(Save-BackupPacotes $pasta)"
    $ok = 0
    foreach ($p in $alvo) {
        if ($Modo -eq 'desativar') { $s = Invoke-Shell "pm disable-user --user 0 $($p.pacote)"; $suc = $s -match 'disabled' }
        else { $s = Invoke-Shell "pm uninstall -k --user 0 $($p.pacote)"; $suc = $s -match 'Success' }
        if ($suc) { $ok++ }
        Add-Registro $pasta 'acoes.jsonl' @{ acao = 'remover'; modo = $Modo; pacote = $p.pacote; sucesso = [bool]$suc; saida = $s.Substring(0, [math]::Min(200, $s.Length)) }
        if ($suc) { Write-Host "  OK $($p.pacote)" -ForegroundColor Green } else { Write-Host "  FALHOU $($p.pacote) ($s)" -ForegroundColor Red }
    }
    Write-Host "`n$ok/$($alvo.Count) concluídos. Reinicie (.\TabletKit.ps1 reiniciar) e use por alguns dias."
    Write-Host 'Algo parou de funcionar? .\TabletKit.ps1 reverter -Pacote NOME  (ou -Tudo)'
}

function Invoke-Reverter {
    $pasta = Get-PastaAparelho
    $estado = @{}
    foreach ($r in (Get-Registros $pasta 'acoes.jsonl')) { if ($r.sucesso) { $estado[$r.pacote] = $r } }
    $pend = @{}; foreach ($k in $estado.Keys) { if ($estado[$k].acao -eq 'remover') { $pend[$k] = $estado[$k] } }
    if ($Tudo) { $alvo = @($pend.Keys) }
    elseif ($Pacote) { $alvo = $Pacote }
    else {
        if (-not $pend.Count) { Write-Host 'O kit não tem nenhuma remoção registrada para este tablet.' }
        else { Write-Host 'Removidos pelo kit (use -Tudo ou -Pacote NOME):'; foreach ($k in $pend.Keys) { Write-Host "  $k  ($($pend[$k].modo), $($pend[$k].data))" } }
        return
    }
    if (-not $alvo.Count) { Write-Host 'Nada para reverter.'; return }
    foreach ($p in $alvo) {
        $modoP = if ($pend.ContainsKey($p)) { $pend[$p].modo } else { 'desinstalar' }
        if ($modoP -eq 'desativar') { $s = Invoke-Shell "pm enable $p"; $suc = $s -match 'enabled' }
        else {
            $s = Invoke-Shell "cmd package install-existing $p"
            if ($s -notmatch 'installed') { $s = Invoke-Shell "pm install-existing $p" }
            $suc = $s -match 'installed'
        }
        Add-Registro $pasta 'acoes.jsonl' @{ acao = 'reverter'; modo = $modoP; pacote = $p; sucesso = [bool]$suc; saida = $s.Substring(0, [math]::Min(200, $s.Length)) }
        if ($suc) { Write-Host "  OK $p" -ForegroundColor Green } else { Write-Host "  FALHOU $p ($s)" -ForegroundColor Red }
    }
}

function Invoke-Otimizar {
    Write-Host 'Otimizações (todas reversíveis):'
    Write-Host "  - Animações em ${Animacao}x (padrão 1x; 0 = desliga)"
    Write-Host '  - Limpar cache de todos os apps (pm trim-caches)'
    if (-not $SemCompilar) { Write-Host '  - Compilar apps em segundo plano (bg-dexopt-job, pode levar 5-20 min)' }
    if (-not $Aplicar) { Write-Host "`nSIMULAÇÃO: nada foi alterado. Rode com -Aplicar." -ForegroundColor Cyan; return }
    $pasta = Get-PastaAparelho
    $antes = Get-Animacoes
    Add-Registro $pasta 'otimizacoes.jsonl' @{ acao = 'antes'; animacoes = $antes }
    foreach ($c in $antes.Keys) { Invoke-Shell "settings put global $c $Animacao" | Out-Null }
    Write-Host '  OK animações'
    Invoke-Shell 'pm trim-caches 999G' | Out-Null; Write-Host '  OK cache'
    if (-not $SemCompilar) { Write-Host '  ... compilando (não desconecte o cabo)'; Invoke-Shell 'cmd package bg-dexopt-job' | Out-Null; Write-Host '  OK compilação' }
    Add-Registro $pasta 'otimizacoes.jsonl' @{ acao = 'aplicado'; animacao = $Animacao }
    Write-Host 'Pronto. Reinicie o tablet: .\TabletKit.ps1 reiniciar'
}

function Invoke-RestaurarOtimizacoes {
    $pasta = Get-PastaAparelho
    $antes = @(Get-Registros $pasta 'otimizacoes.jsonl' | Where-Object { $_.acao -eq 'antes' })
    foreach ($c in (Get-Animacoes).Keys) {
        $v = '1'
        if ($antes.Count -and $antes[0].animacoes.$c -and $antes[0].animacoes.$c -ne 'null') { $v = $antes[0].animacoes.$c }
        Invoke-Shell "settings put global $c $v" | Out-Null
    }
    Write-Host 'OK Animações restauradas. (Cache limpo e compilação não precisam ser desfeitos.)' -ForegroundColor Green
}

# ----------------------------------------------------------------- main
try {
    $Adb = Find-Adb
    Select-Aparelho
    switch ($Acao) {
        'verificar' { Invoke-Verificar }
        'varrer' { Invoke-Varrer }
        'medir' { Invoke-Medir }
        'remover' { Invoke-Remover }
        'reverter' { Invoke-Reverter }
        'otimizar' { Invoke-Otimizar }
        'restaurar-otimizacoes' { Invoke-RestaurarOtimizacoes }
        'reiniciar' { Invoke-Adb @('reboot') | Out-Null; Write-Host 'OK Reiniciando o tablet. Espere ele ligar (e uns 2 min) antes de medir de novo.' -ForegroundColor Green }
    }
} catch {
    Write-Host "ERRO: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
