#!/bin/sh
# Instala este repositório como skill do Claude Code (~/.claude/skills).
# Uso: sh scripts/instalar-skill.sh            (cria um link simbólico)
#      sh scripts/instalar-skill.sh --desinstalar
set -e
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="$HOME/.claude/skills/tablet-sem-defeito-programado"

if [ "$1" = "--desinstalar" ]; then
    rm -rf "$DESTINO" && echo "Skill removida de $DESTINO"
    exit 0
fi
if [ "$RAIZ" = "$DESTINO" ]; then echo "Este repositório já está na pasta de skills."; exit 0; fi
mkdir -p "$HOME/.claude/skills"
if [ -e "$DESTINO" ]; then
    echo "Já existe algo em $DESTINO. Rode com --desinstalar antes, se quiser reinstalar."
    exit 1
fi
ln -s "$RAIZ" "$DESTINO"
echo "Skill instalada: $DESTINO -> $RAIZ"
echo "Abra uma nova conversa no Claude Code e peça, por exemplo: 'deixe meu tablet mais rápido'."
