"""Gera dist/tablet-sem-defeito-programado.zip para enviar como skill ao claude.ai
(Configurações > Capacidades > Skills > Enviar skill) ou a outra plataforma que aceite skills em .zip.

Uso: python scripts/empacotar-skill.py
"""
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NOME = "tablet-sem-defeito-programado"
INCLUIR = ["SKILL.md", "AGENTS.md", "README.md", "LICENSE", "CONTRIBUTING.md",
           "dados", "docs", "python", "powershell", "scripts"]
IGNORAR = {"__pycache__", ".pyc"}


def main() -> None:
    destino = RAIZ / "dist" / f"{NOME}.zip"
    destino.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for item in INCLUIR:
            caminho = RAIZ / item
            arquivos = [caminho] if caminho.is_file() else sorted(p for p in caminho.rglob("*") if p.is_file())
            for arq in arquivos:
                if any(parte in IGNORAR for parte in arq.parts) or arq.suffix in IGNORAR:
                    continue
                z.write(arq, f"{NOME}/{arq.relative_to(RAIZ).as_posix()}")
    print(f"✔ {destino} ({destino.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
