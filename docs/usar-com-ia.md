# Usar com um assistente de IA

O repositório funciona como **skill**: um roteiro ([SKILL.md](../SKILL.md)) que ensina o assistente a fazer a varredura, propor um plano, pedir sua confirmação e aplicar as mudanças com segurança. Escolha o seu caso:

## Claude Code (terminal, app de desktop ou extensão)

Instale como skill pessoal. Ela fica disponível em qualquer pasta:

```bash
git clone https://github.com/RobertBorges98/tablet-sem-defeito-programado.git
cd tablet-sem-defeito-programado
```
- **Windows:** `powershell -ExecutionPolicy Bypass -File scripts\instalar-skill.ps1`
- **Linux/Mac:** `sh scripts/instalar-skill.sh`

Depois, numa conversa nova, conecte o tablet e peça, por exemplo: *"deixe meu tablet mais rápido"* ou *"meu tablet fica mostrando que um app parou"*.

Também funciona sem instalar: abra o Claude Code dentro da pasta do repositório. O `CLAUDE.md` já aponta para as instruções.

## claude.ai (site ou app)

1. Rode `python scripts/empacotar-skill.py`. Ele gera `dist/tablet-sem-defeito-programado.zip`.
2. No claude.ai, envie o .zip em **Configurações > Capacidades > Skills**.

No site, o Claude não acessa o cabo USB do seu computador. Ele vai orientar e interpretar o que você colar. Para que ele rode os comandos sozinho, use o Claude Code.

## Codex, Cursor, GitHub Copilot, Gemini CLI, Aider e outros agentes

Abra a pasta do repositório no agente. Esses agentes leem o [AGENTS.md](../AGENTS.md) automaticamente, e ele aponta para o roteiro do `SKILL.md`. Se o seu agente não ler, diga a ele: *"siga as instruções do SKILL.md"*.

## ChatGPT, Gemini ou outro chat sem acesso ao computador

Você roda os comandos, e o assistente interpreta. Cole o prompt abaixo junto com o conteúdo do [SKILL.md](../SKILL.md):

```text
Você vai me ajudar a otimizar um tablet Android usando o kit "Tablet sem Obsolescência".
As regras e o fluxo estão no SKILL.md que colei abaixo. Siga as regras de segurança à risca.
Você não tem acesso ao meu computador: me diga UM comando por vez para eu rodar na pasta do kit,
espere eu colar a saída e só então continue. Antes de qualquer comando com --aplicar,
me mostre o plano em tabela e espere eu confirmar. Comece pelo comando "verificar".

[cole aqui o conteúdo do SKILL.md]
```

> Privacidade: ao colar o relatório da varredura em um chat online, apague antes a linha do **serial** e, se quiser, a lista dos seus apps.
