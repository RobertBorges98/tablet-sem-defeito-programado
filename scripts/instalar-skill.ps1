<#
.SYNOPSIS
  Instala este repositório como skill do Claude Code (pasta ~/.claude/skills).

.DESCRIPTION
  Por padrão cria um "atalho" (junction) apontando para esta pasta, então um
  'git pull' aqui atualiza a skill também. Não precisa de administrador.
  Com -Copiar, copia os arquivos em vez de criar o atalho.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\instalar-skill.ps1
  powershell -ExecutionPolicy Bypass -File scripts\instalar-skill.ps1 -Copiar
  powershell -ExecutionPolicy Bypass -File scripts\instalar-skill.ps1 -Desinstalar
#>
param([switch]$Copiar, [switch]$Desinstalar)
$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $PSScriptRoot
$Nome = 'tablet-sem-defeito-programado'
$Pasta = Join-Path $HOME ".claude\skills"
$Destino = Join-Path $Pasta $Nome

if ($Desinstalar) {
    if (Test-Path $Destino) {
        $item = Get-Item $Destino -Force
        if ($item.LinkType) { $item.Delete() } else { Remove-Item $Destino -Recurse -Force }
        Write-Host "OK Skill removida de $Destino" -ForegroundColor Green
    } else { Write-Host "A skill não estava instalada." }
    exit 0
}

if ((Resolve-Path $Raiz).Path -eq $Destino) { Write-Host "Este repositório já está na pasta de skills." -ForegroundColor Green; exit 0 }
New-Item -ItemType Directory -Force $Pasta | Out-Null
if (Test-Path $Destino) {
    Write-Host "Já existe algo em $Destino. Rode com -Desinstalar antes, se quiser reinstalar." -ForegroundColor Yellow
    exit 1
}

if ($Copiar) {
    New-Item -ItemType Directory $Destino | Out-Null
    $itens = 'SKILL.md', 'AGENTS.md', 'README.md', 'LICENSE', 'CONTRIBUTING.md', 'dados', 'docs', 'python', 'powershell', 'scripts'
    foreach ($i in $itens) { Copy-Item (Join-Path $Raiz $i) $Destino -Recurse }
    Write-Host "OK Skill copiada para $Destino" -ForegroundColor Green
} else {
    New-Item -ItemType Junction -Path $Destino -Target $Raiz | Out-Null
    Write-Host "OK Skill instalada: $Destino -> $Raiz" -ForegroundColor Green
}
Write-Host "Abra uma nova conversa no Claude Code e peça, por exemplo: 'deixe meu tablet mais rápido'."
