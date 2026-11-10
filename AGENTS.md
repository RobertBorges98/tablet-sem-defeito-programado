# Instruções para assistentes de IA

Este repositório é um kit para **varrer e otimizar tablets/celulares Android via ADB** (sem root, reversível). Ele vale para Claude Code, Codex, Cursor, GitHub Copilot, Gemini CLI, Aider e outros agentes que leem `AGENTS.md`.

## Se a pessoa quer otimizar ou consertar um aparelho Android

Siga o roteiro completo em **[SKILL.md](SKILL.md)**. Lá estão as regras de segurança, o fluxo recomendado, a referência de comandos e as armadilhas encontradas em aparelhos reais. Resumo das regras:

- Simule primeiro e só rode com `--aplicar` depois que a pessoa confirmar.
- Nunca contorne o bloqueio de pacotes `perigoso`.
- Pergunte o que a pessoa usa antes de remover apps com que ela interage.
- Em aparelho de criança, preserve o Family Link e o Bem-estar digital.
- Não apague dados de apps sem pedido explícito.
- `relatorios/` é privado: nunca publique nem envie para fora do computador.

## Se a pessoa quer mudar o código

- `python/tabletkit.py` (Python 3.10+, só biblioteca padrão) e `powershell/TabletKit.ps1` (PowerShell 5.1+) precisam ter **os mesmos comandos e o mesmo comportamento**. Se mudar um, mude o outro.
- Os arquivos `.ps1` ficam em **UTF-8 com BOM** e quebra de linha CRLF, porque o PowerShell 5.1 corrompe acentos sem BOM.
- Banco de pacotes: `dados/pacotes.json` (veja `CONTRIBUTING.md`).
- Testes: `python -m unittest discover tests`. Eles usam um ADB falso (`tests/adb_falso.py`) e não precisam de aparelho. O CI roda em Windows e Linux.
- Toda ação que altera o aparelho precisa simular por padrão, pedir confirmação, registrar em `acoes.jsonl` e poder ser revertida.
