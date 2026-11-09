#!/usr/bin/env python3
"""
Tablet sem Obsolescência — kit de varredura e limpeza via ADB (sem root).

Uso rápido:
    python tabletkit.py verificar          # o tablet está conectado?
    python tabletkit.py varrer             # diagnóstico completo + relatório
    python tabletkit.py medir              # mede RAM livre e tempo de abertura
    python tabletkit.py remover            # SIMULA a remoção dos apps "seguros"
    python tabletkit.py remover --aplicar  # remove de verdade (pede confirmação)
    python tabletkit.py reverter --tudo    # desfaz tudo que o kit removeu
    python tabletkit.py otimizar --aplicar # animações, cache e compilação
    python tabletkit.py restaurar-otimizacoes
    python tabletkit.py reiniciar

Tudo o que o kit faz é reversível: os apps são removidos só para o usuário 0
(`pm uninstall --user 0`) e continuam guardados na partição do sistema.
Só usa a biblioteca padrão do Python 3.10+.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "dados" / "pacotes.json"
RELATORIOS = RAIZ / "relatorios"
NIVEL_RISCO = {"seguro": 0, "cuidado": 1, "perigoso": 2}
SAUDE_BATERIA = {
    "1": "desconhecida", "2": "boa", "3": "superaquecida", "4": "morta",
    "5": "sobretensão", "6": "falha", "7": "fria",
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# ADB
# --------------------------------------------------------------------------- #
class ErroKit(Exception):
    pass


def achar_adb() -> str:
    candidatos = [
        os.environ.get("TABLETKIT_ADB"),
        shutil.which("adb"),
        str(RAIZ / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")),
    ]
    for c in candidatos:
        if c and Path(c).exists():
            return c
    raise ErroKit(
        "ADB não encontrado.\n"
        "  • Windows: rode  powershell -File scripts\\instalar-adb.ps1\n"
        "  • Linux:   sudo apt install adb    • Mac: brew install android-platform-tools\n"
        "  • Ou defina a variável TABLETKIT_ADB com o caminho do adb."
    )


class Tablet:
    def __init__(self, serial: str | None = None):
        self.adb = achar_adb()
        self.serial = serial or self._escolher_aparelho()

    def _rodar(self, args: list[str], timeout: int = 120) -> tuple[int, str]:
        base = [self.adb] + (["-s", self.serial] if getattr(self, "serial", None) else [])
        try:
            r = subprocess.run(base + args, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            return 124, "tempo esgotado"
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def _escolher_aparelho(self) -> str:
        _, saida = self._rodar(["devices"])
        prontos, outros = [], []
        for linha in saida.splitlines()[1:]:
            partes = linha.split()
            if len(partes) >= 2:
                (prontos if partes[1] == "device" else outros).append(partes)
        if not prontos:
            msg = "Nenhum tablet conectado.\n"
            if any(p[1] == "unauthorized" for p in outros):
                msg += "  → Desbloqueie o tablet e aceite 'Permitir depuração USB'.\n"
            msg += ("  → Confira: Opções do desenvolvedor > Depuração USB ligada, cabo de dados "
                    "(não só de carga) e rode 'adb devices'.")
            raise ErroKit(msg)
        if len(prontos) > 1:
            lista = ", ".join(p[0] for p in prontos)
            raise ErroKit(f"Mais de um aparelho conectado ({lista}). Use --serial SERIAL.")
        return prontos[0][0]

    def shell(self, comando: str, timeout: int = 120) -> str:
        return self._rodar(["shell", comando], timeout)[1].strip()

    def prop(self, nome: str) -> str:
        return self.shell(f"getprop {nome}")

    def pacotes(self, flag: str = "") -> set[str]:
        saida = self.shell(f"pm list packages {flag}".strip())
        return {l.split(":", 1)[1].strip() for l in saida.splitlines() if l.startswith("package:")}


# --------------------------------------------------------------------------- #
# Banco de pacotes
# --------------------------------------------------------------------------- #
class Banco:
    def __init__(self, caminho: Path = BANCO):
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        self.por_pacote = {p["pacote"]: p for p in dados["pacotes"]}
        self.suspeitos = dados.get("padroes_suspeitos", [])
        self.prefixos_perigosos = dados.get("prefixos_perigosos", [])
        self.legenda_categoria = dados.get("legenda_categoria", {})
        self.ocultos = dados.get("padroes_ocultos", {}).get("contem", [])
        comp = dados.get("componentes_sistema", {})
        self.componentes = set(comp.get("pacotes", []))
        self.motivo_componente = comp.get("motivo", "Componente do sistema.")

    def oculto(self, pacote: str) -> bool:
        """Overlays/recursos não catalogados: não rodam nem gastam RAM, ficam fora do relatório."""
        return pacote not in self.por_pacote and any(s in pacote for s in self.ocultos)

    def classificar(self, pacote: str) -> dict:
        if pacote in self.por_pacote:
            return self.por_pacote[pacote]
        if pacote in self.componentes:
            return {"pacote": pacote, "nome": pacote, "categoria": "essencial",
                    "risco": "perigoso", "motivo": self.motivo_componente}
        for pre in self.prefixos_perigosos:
            if pacote.startswith(pre):
                return {"pacote": pacote, "nome": pacote, "categoria": "essencial",
                        "risco": "perigoso", "motivo": "Componente do sistema (por prefixo)."}
        for s in self.suspeitos:
            if pacote.startswith(s["prefixo"]):
                return {"pacote": pacote, "nome": pacote, "categoria": "suspeito",
                        "risco": "verificar", "motivo": s["motivo"]}
        return {"pacote": pacote, "nome": pacote, "categoria": "nao_catalogado",
                "risco": "verificar", "motivo": "Não está no banco. Pesquise antes de remover."}

    def bloqueado(self, pacote: str) -> bool:
        return self.classificar(pacote)["risco"] == "perigoso"


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def agora() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def pasta_do_aparelho(t: Tablet) -> Path:
    modelo = re.sub(r"[^A-Za-z0-9_-]", "_", t.prop("ro.product.model") or "tablet")
    serial = re.sub(r"[^A-Za-z0-9_-]", "_", t.serial)
    p = RELATORIOS / f"{modelo}_{serial}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def registrar(pasta: Path, arquivo: str, registro: dict) -> None:
    with open(pasta / arquivo, "a", encoding="utf-8") as f:
        f.write(json.dumps({"data": agora(), **registro}, ensure_ascii=False) + "\n")


def ler_registros(pasta: Path, arquivo: str) -> list[dict]:
    caminho = pasta / arquivo
    if not caminho.exists():
        return []
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()]


def salvar_backup_pacotes(t: Tablet, pasta: Path) -> Path:
    destino = pasta / f"pacotes-ativos-{dt.datetime.now():%Y%m%d-%H%M%S}.txt"
    destino.write_text("\n".join(sorted(t.pacotes("-e"))) + "\n", encoding="utf-8")
    return destino


def confirmar(pergunta: str, automatico: bool) -> bool:
    if automatico:
        return True
    try:
        return input(f"{pergunta} Digite SIM para continuar: ").strip().upper() == "SIM"
    except EOFError:
        return False


def kb_para_gb(kb: float) -> str:
    return f"{kb / 1024 / 1024:.2f} GB"


# --------------------------------------------------------------------------- #
# Coleta de diagnóstico
# --------------------------------------------------------------------------- #
def info_aparelho(t: Tablet) -> dict:
    props = {
        "fabricante": "ro.product.manufacturer", "modelo": "ro.product.model",
        "codinome": "ro.product.device", "android": "ro.build.version.release",
        "sdk": "ro.build.version.sdk", "patch_seguranca": "ro.build.version.security_patch",
        "abi": "ro.product.cpu.abi", "plataforma": "ro.board.platform",
        "build": "ro.build.display.id",
    }
    info = {k: t.prop(v) for k, v in props.items()}
    info["serial"] = t.serial
    return info


def memoria(t: Tablet) -> dict:
    valores = {}
    for linha in t.shell("cat /proc/meminfo").splitlines():
        m = re.match(r"(\w+):\s+(\d+)", linha)
        if m:
            valores[m.group(1)] = int(m.group(2))
    return {"total_kb": valores.get("MemTotal", 0), "disponivel_kb": valores.get("MemAvailable", 0),
            "swap_total_kb": valores.get("SwapTotal", 0), "swap_livre_kb": valores.get("SwapFree", 0)}


def armazenamento(t: Tablet) -> dict:
    linhas = t.shell("df -k /data").splitlines()
    for linha in linhas[1:]:
        p = linha.split()
        if len(p) >= 4 and p[1].isdigit():
            total, usado, livre = int(p[1]), int(p[2]), int(p[3])
            return {"total_kb": total, "usado_kb": usado, "livre_kb": livre,
                    "uso_pct": round(usado * 100 / total, 1) if total else 0}
    return {}


def bateria(t: Tablet) -> dict:
    b = {}
    for linha in t.shell("dumpsys battery").splitlines():
        if ":" in linha:
            k, v = linha.split(":", 1)
            b[k.strip()] = v.strip()
    temp = b.get("temperature")
    return {
        "nivel_pct": b.get("level"),
        "saude": SAUDE_BATERIA.get(b.get("health", ""), b.get("health")),
        "temperatura_c": round(int(temp) / 10, 1) if temp and temp.lstrip("-").isdigit() else None,
        "tensao_mv": b.get("voltage"),
        "ciclos": b.get("cycle_count") or b.get("mSavedBatteryUsage"),
    }


def animacoes(t: Tablet) -> dict:
    chaves = ["window_animation_scale", "transition_animation_scale", "animator_duration_scale"]
    return {c: t.shell(f"settings get global {c}") for c in chaves}


def apps_que_iniciam_sozinhos(t: Tablet) -> list[str]:
    saida = t.shell("cmd package query-receivers --brief -a android.intent.action.BOOT_COMPLETED")
    pacotes = set()
    for linha in saida.splitlines():
        linha = linha.strip()
        if "/" in linha and not linha.startswith(("Error", "Exception")):
            pacotes.add(linha.split("/", 1)[0])
    return sorted(pacotes)


def maiores_consumidores_ram(t: Tablet, limite: int = 15) -> list[dict]:
    saida = t.shell("dumpsys meminfo", timeout=180)
    resultado, dentro = [], False
    for linha in saida.splitlines():
        if re.search(r"Total (PSS|RSS) by process", linha):
            if resultado:
                break
            dentro = True
            continue
        if dentro:
            m = re.match(r"\s*([\d,]+)K: (\S+) \(pid", linha)
            if m:
                resultado.append({"pacote": m.group(2), "ram_mb": round(int(m.group(1).replace(",", "")) / 1024, 1)})
            elif resultado and not linha.strip():
                break
        if len(resultado) >= limite:
            break
    return resultado


def tempo_abertura_config(t: Tablet, vezes: int = 3) -> float | None:
    tempos = []
    for _ in range(vezes):
        t.shell("am force-stop com.android.settings")
        saida = t.shell("am start -W -n com.android.settings/.Settings")
        m = re.search(r"TotalTime:\s*(\d+)", saida)
        if m:
            tempos.append(int(m.group(1)))
    t.shell("input keyevent KEYCODE_HOME")
    return round(sum(tempos) / len(tempos)) if tempos else None


# --------------------------------------------------------------------------- #
# Comandos
# --------------------------------------------------------------------------- #
def cmd_verificar(args) -> None:
    t = Tablet(args.serial)
    i = info_aparelho(t)
    print(f"✔ Conectado: {i['fabricante']} {i['modelo']} ({i['codinome']}) — Android {i['android']} "
          f"(SDK {i['sdk']}), serial {t.serial}")


def cmd_varrer(args) -> None:
    t, banco = Tablet(args.serial), Banco()
    pasta = pasta_do_aparelho(t)
    print("Varrendo o tablet... (pode levar 1 a 2 minutos)")

    info = info_aparelho(t)
    ativos, desativados = t.pacotes("-e"), t.pacotes("-d")
    sistema, todos_u = t.pacotes("-s"), t.pacotes("-u")
    instalados = t.pacotes()
    removidos = todos_u - instalados

    classificados = {"seguro": [], "cuidado": [], "perigoso": [], "verificar": []}
    ocultos = 0
    for p in sorted(ativos):
        c = dict(banco.classificar(p))
        c["sistema"] = p in sistema
        if c["risco"] == "verificar":
            if not c["sistema"]:      # app de terceiro não catalogado: escolha do usuário
                continue
            if banco.oculto(p):       # overlay/recurso: não roda, não gasta RAM
                ocultos += 1
                continue
        classificados[c["risco"]].append(c)

    boot = apps_que_iniciam_sozinhos(t)
    diag = {
        "data": agora(), "aparelho": info, "memoria": memoria(t),
        "armazenamento": armazenamento(t), "bateria": bateria(t), "animacoes": animacoes(t),
        "contagem": {"ativos": len(ativos), "desativados": len(desativados),
                     "sistema": len(sistema), "terceiros": len(ativos - sistema),
                     "removidos_usuario0": len(removidos), "overlays_ocultos": ocultos},
        "classificacao": classificados,
        "iniciam_no_boot": [{"pacote": p, "terceiro": p not in sistema,
                             **{k: banco.classificar(p)[k] for k in ("risco", "categoria")}}
                            for p in boot if p in ativos],
        "maiores_consumidores_ram": maiores_consumidores_ram(t),
        "ja_removidos": sorted(removidos), "desativados": sorted(desativados),
    }

    carimbo = f"{dt.datetime.now():%Y%m%d-%H%M%S}"
    (pasta / f"varredura-{carimbo}.json").write_text(json.dumps(diag, ensure_ascii=False, indent=2), encoding="utf-8")
    md = pasta / f"varredura-{carimbo}.md"
    md.write_text(relatorio_markdown(diag, banco), encoding="utf-8")
    salvar_backup_pacotes(t, pasta)
    imprimir_resumo(diag)
    print(f"\nRelatório completo: {md}")


def relatorio_markdown(d: dict, banco: Banco) -> str:
    a, m, s, b = d["aparelho"], d["memoria"], d["armazenamento"], d["bateria"]
    c, q = d["classificacao"], d["contagem"]
    L = [f"# Varredura — {a['fabricante']} {a['modelo']}", "",
         f"Data: {d['data']}", "", "## Aparelho", "",
         "| Item | Valor |", "|---|---|"]
    for k, v in a.items():
        if k != "serial":
            L.append(f"| {k} | {v} |")
    L += ["", "## Saúde", "",
          f"- **RAM:** {kb_para_gb(m['disponivel_kb'])} livres de {kb_para_gb(m['total_kb'])}",
          f"- **Armazenamento:** {kb_para_gb(s.get('livre_kb', 0))} livres "
          f"({s.get('uso_pct', '?')}% usado)" + ("  ⚠️ acima de 85% deixa o tablet lento" if s.get("uso_pct", 0) > 85 else ""),
          f"- **Bateria:** {b['nivel_pct']}%, saúde {b['saude']}, {b['temperatura_c']} °C",
          f"- **Animações:** {' / '.join(d['animacoes'].values())} (janela / transição / duração)",
          f"- **Pacotes:** {q['ativos']} ativos ({q['sistema']} do sistema, {q['terceiros']} de terceiros), "
          f"{q['desativados']} desativados, {q['removidos_usuario0']} já removidos, "
          f"{q['overlays_ocultos']} overlays ocultos", ""]
    L += alertas(d)
    rotulos = [("seguro", "✅ Pode remover"), ("cuidado", "⚠️ Remover com cuidado"),
               ("verificar", "🔎 Apps do sistema não catalogados (pesquise antes)"),
               ("perigoso", "⛔ Essenciais (o kit não remove)")]
    for chave, titulo in rotulos:
        L += ["", f"## {titulo} — {len(c[chave])}", ""]
        if not c[chave]:
            L.append("_nenhum_")
            continue
        L += ["| Pacote | Nome | Categoria | Motivo |", "|---|---|---|---|"]
        for p in c[chave]:
            L.append(f"| `{p['pacote']}` | {p['nome']} | {p['categoria']} | {p['motivo']} |")
    boot_sis = [x for x in d["iniciam_no_boot"] if not x["terceiro"]]
    boot_ter = [x for x in d["iniciam_no_boot"] if x["terceiro"]]
    L += ["", f"## Apps de terceiros que iniciam sozinhos ao ligar — {len(boot_ter)}", "",
          "Instalados por você, pela loja ou pré-carregados pelo fabricante. Desinstale pela Play Store os que não usa.", ""]
    L += [f"- `{x['pacote']}`" + (f" ({x['risco']})" if x["risco"] != "verificar" else "") for x in boot_ter] or ["_nenhum_"]
    L += ["", f"## Apps do sistema que iniciam sozinhos ao ligar — {len(boot_sis)}", ""]
    L += [f"- `{x['pacote']}` ({x['risco']})" for x in boot_sis] or ["_nenhum_"]
    L += ["", "## Maiores consumidores de RAM agora", ""]
    L += [f"- `{x['pacote']}` — {x['ram_mb']} MB" for x in d["maiores_consumidores_ram"]] or ["_não disponível_"]
    L += ["", "---", "Próximo passo: `python tabletkit.py remover` (simulação) e depois `--aplicar`.", ""]
    return "\n".join(L)


def alertas(d: dict) -> list[str]:
    out = []
    a, s, b = d["aparelho"], d["armazenamento"], d["bateria"]
    ativos = {p["pacote"] for lista in d["classificacao"].values() for p in lista}
    if "com.samsung.android.game.gos" in ativos:
        out.append("- ⚠️ **Game Optimizing Service ativo:** limita o desempenho de jogos e apps pesados.")
    if ativos & {"com.wssyncmldm", "com.sec.android.soagent"}:
        out.append("- ℹ️ **Atualizações automáticas ativas.** Em tablets antigos, versões novas podem pesar mais. "
                   "Bloquear atualizações também bloqueia correções de segurança: decida com cuidado.")
    if s.get("uso_pct", 0) > 85:
        out.append("- ⚠️ **Armazenamento quase cheio.** Acima de ~85% o sistema de arquivos fica lento.")
    if b.get("saude") not in (None, "boa", "desconhecida"):
        out.append(f"- ⚠️ **Bateria com saúde '{b['saude']}'.** Bateria gasta faz o sistema reduzir a CPU; "
                   "trocar a bateria pode ser a melhor 'otimização'.")
    if b.get("temperatura_c") and b["temperatura_c"] >= 40:
        out.append("- ⚠️ **Tablet quente (≥ 40 °C).** O sistema reduz a velocidade para esfriar.")
    try:
        ano = int((a.get("patch_seguranca") or "0")[:4])
        if ano and dt.date.today().year - ano >= 2:
            out.append(f"- ℹ️ **Patch de segurança de {a['patch_seguranca']}.** O fabricante parou de atualizar; "
                       "cuidado com bancos e apps sensíveis.")
    except ValueError:
        pass
    sujos = [x["pacote"] for x in d["iniciam_no_boot"] if x["categoria"] in ("propaganda", "telemetria")]
    if sujos:
        out.append(f"- ⚠️ **{len(sujos)} apps de propaganda/telemetria iniciam junto com o tablet.**")
    return (["## Alertas", ""] + out) if out else []


def imprimir_resumo(d: dict) -> None:
    a, m, c = d["aparelho"], d["memoria"], d["classificacao"]
    print(f"\n{a['fabricante']} {a['modelo']} — Android {a['android']} — "
          f"RAM livre {kb_para_gb(m['disponivel_kb'])} / {kb_para_gb(m['total_kb'])}")
    print(f"  ✅ removíveis: {len(c['seguro'])}   ⚠️ com cuidado: {len(c['cuidado'])}   "
          f"🔎 não catalogados: {len(c['verificar'])}   ⛔ essenciais: {len(c['perigoso'])}")
    for linha in alertas(d)[2:]:
        print(" ", linha.lstrip("- ").replace("**", ""))


def cmd_medir(args) -> None:
    t = Tablet(args.serial)
    pasta = pasta_do_aparelho(t)
    print("Medindo (abre as Configurações 3 vezes)...")
    med = {"ram_livre_kb": memoria(t)["disponivel_kb"], "apps_ativos": len(t.pacotes("-e")),
           "abrir_config_ms": tempo_abertura_config(t), "rotulo": args.rotulo or ""}
    anteriores = ler_registros(pasta, "medicoes.jsonl")
    registrar(pasta, "medicoes.jsonl", med)
    print(f"  RAM livre: {kb_para_gb(med['ram_livre_kb'])} | apps ativos: {med['apps_ativos']} | "
          f"Configurações abriram em {med['abrir_config_ms']} ms")
    if anteriores:
        p = anteriores[0]
        print(f"\nComparado com a 1ª medição ({p['data']}{' - ' + p['rotulo'] if p.get('rotulo') else ''}):")
        print(f"  RAM livre: {kb_para_gb(p['ram_livre_kb'])} → {kb_para_gb(med['ram_livre_kb'])}")
        print(f"  Apps ativos: {p['apps_ativos']} → {med['apps_ativos']}")
        if p.get("abrir_config_ms") and med["abrir_config_ms"]:
            ganho = (p["abrir_config_ms"] - med["abrir_config_ms"]) / p["abrir_config_ms"] * 100
            print(f"  Abertura: {p['abrir_config_ms']} → {med['abrir_config_ms']} ms ({ganho:+.0f}% mais rápido)")
        print("  (Para comparar de forma justa, reinicie o tablet e espere 2 min antes de medir.)")


def cmd_remover(args) -> None:
    t, banco = Tablet(args.serial), Banco()
    ativos = t.pacotes("-e")
    alvo: list[dict] = []
    if args.pacote:
        for p in args.pacote:
            info = banco.classificar(p)
            if p not in ativos:
                print(f"  ↷ {p}: não está instalado/ativo, ignorado.")
            elif info["risco"] == "perigoso":
                print(f"  ⛔ {p}: ESSENCIAL ({info['motivo']}) — bloqueado.")
            else:
                if info["risco"] == "verificar":
                    print(f"  ⚠️ {p}: não catalogado. Você assume o risco.")
                alvo.append(info)
    else:
        limite = NIVEL_RISCO[args.risco]
        for p in sorted(ativos):
            info = banco.classificar(p)
            if info["risco"] in NIVEL_RISCO and NIVEL_RISCO[info["risco"]] <= limite and info["risco"] != "perigoso":
                if not args.categoria or info["categoria"] in args.categoria:
                    alvo.append(info)

    if not alvo:
        print("Nada para remover com esses filtros.")
        return
    acao = "DESATIVAR" if args.modo == "desativar" else "REMOVER (usuário 0)"
    print(f"\n{len(alvo)} app(s) para {acao}:")
    for p in alvo:
        print(f"  [{p['risco']:>8}] {p['pacote']:<50} {p['nome']} — {p['motivo']}")

    if not args.aplicar:
        print("\nSIMULAÇÃO: nada foi alterado. Rode de novo com --aplicar para executar.")
        return
    if not confirmar(f"\nIsso vai {acao.lower()} {len(alvo)} app(s). É reversível com 'reverter'.", args.sim):
        print("Cancelado.")
        return

    pasta = pasta_do_aparelho(t)
    print(f"Backup da lista de apps: {salvar_backup_pacotes(t, pasta)}")
    ok = 0
    for p in alvo:
        if args.modo == "desativar":
            saida = t.shell(f"pm disable-user --user 0 {p['pacote']}")
            sucesso = "disabled" in saida.lower()
        else:
            saida = t.shell(f"pm uninstall -k --user 0 {p['pacote']}")
            sucesso = "Success" in saida
        ok += sucesso
        registrar(pasta, "acoes.jsonl", {"acao": "remover", "modo": args.modo, "pacote": p["pacote"],
                                         "sucesso": sucesso, "saida": saida[:200]})
        print(f"  {'✔' if sucesso else '✘'} {p['pacote']}" + ("" if sucesso else f"  ({saida[:120]})"))
    print(f"\n{ok}/{len(alvo)} concluídos. Reinicie (python tabletkit.py reiniciar) e use por alguns dias.")
    print("Algo parou de funcionar? python tabletkit.py reverter --pacote NOME  (ou --tudo)")


def cmd_reverter(args) -> None:
    t = Tablet(args.serial)
    pasta = pasta_do_aparelho(t)
    historico = ler_registros(pasta, "acoes.jsonl")
    # estado mais recente de cada pacote
    estado: dict[str, dict] = {}
    for r in historico:
        if r.get("sucesso"):
            estado[r["pacote"]] = r
    pendentes = {p: r for p, r in estado.items() if r["acao"] == "remover"}

    if args.tudo:
        alvo = list(pendentes)
    elif args.pacote:
        alvo = args.pacote
    else:
        if not pendentes:
            print("O kit não tem nenhuma remoção registrada para este tablet.")
        else:
            print("Removidos pelo kit (use --tudo ou --pacote NOME):")
            for p, r in pendentes.items():
                print(f"  {p}  ({r['modo']}, {r['data']})")
        return
    if not alvo:
        print("Nada para reverter.")
        return

    for p in alvo:
        modo = pendentes.get(p, {}).get("modo", "desinstalar")
        if modo == "desativar":
            saida = t.shell(f"pm enable {p}")
            sucesso = "enabled" in saida.lower()
        else:
            saida = t.shell(f"cmd package install-existing {p}")
            if "installed" not in saida.lower():
                saida = t.shell(f"pm install-existing {p}")
            sucesso = "installed" in saida.lower()
        registrar(pasta, "acoes.jsonl", {"acao": "reverter", "modo": modo, "pacote": p,
                                         "sucesso": sucesso, "saida": saida[:200]})
        print(f"  {'✔' if sucesso else '✘'} {p}" + ("" if sucesso else f"  ({saida[:120]})"))


def cmd_otimizar(args) -> None:
    t = Tablet(args.serial)
    v = args.animacao
    passos = [f"Animações em {v}x (padrão 1x; 0 = desliga)", "Limpar cache de todos os apps (pm trim-caches)"]
    if not args.sem_compilar:
        passos.append("Compilar apps em segundo plano (bg-dexopt-job, pode levar 5-20 min)")
    print("Otimizações (todas reversíveis):")
    for p in passos:
        print(f"  • {p}")
    if not args.aplicar:
        print("\nSIMULAÇÃO: nada foi alterado. Rode com --aplicar.")
        return
    pasta = pasta_do_aparelho(t)
    registrar(pasta, "otimizacoes.jsonl", {"acao": "antes", "animacoes": animacoes(t)})
    for chave in animacoes(t):
        t.shell(f"settings put global {chave} {v}")
    print("  ✔ animações")
    t.shell("pm trim-caches 999G", timeout=300)
    print("  ✔ cache")
    if not args.sem_compilar:
        print("  … compilando (não desconecte o cabo)")
        t.shell("cmd package bg-dexopt-job", timeout=3600)
        print("  ✔ compilação")
    registrar(pasta, "otimizacoes.jsonl", {"acao": "aplicado", "animacao": v})
    print("Pronto. Reinicie o tablet: python tabletkit.py reiniciar")


def cmd_restaurar_otimizacoes(args) -> None:
    t = Tablet(args.serial)
    pasta = pasta_do_aparelho(t)
    antes = [r for r in ler_registros(pasta, "otimizacoes.jsonl") if r["acao"] == "antes"]
    originais = antes[0]["animacoes"] if antes else {}
    for chave in animacoes(t):
        valor = originais.get(chave) or "1"
        if valor in ("null", ""):
            valor = "1"
        t.shell(f"settings put global {chave} {valor}")
    print("✔ Animações restauradas. (Cache limpo e compilação não precisam ser desfeitos.)")


def cmd_reiniciar(args) -> None:
    t = Tablet(args.serial)
    t._rodar(["reboot"])
    print("✔ Reiniciando o tablet. Espere ele ligar (e uns 2 min) antes de medir de novo.")


# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tabletkit", description="Tablet sem Obsolescência — varredura e limpeza via ADB")
    ap.add_argument("--serial", help="serial do aparelho (se houver mais de um conectado)")
    sub = ap.add_subparsers(dest="comando", required=True)

    sub.add_parser("verificar", help="confere se o tablet está conectado")
    sub.add_parser("varrer", help="diagnóstico completo e relatório")
    s = sub.add_parser("medir", help="mede RAM livre e tempo de abertura (antes/depois)")
    s.add_argument("--rotulo", help="ex.: antes, depois")

    s = sub.add_parser("remover", help="remove/desativa apps (simula por padrão)")
    s.add_argument("--risco", choices=["seguro", "cuidado"], default="seguro",
                   help="nível máximo de risco aceito (padrão: seguro)")
    s.add_argument("--categoria", nargs="+", help="ex.: propaganda telemetria limitador")
    s.add_argument("--pacote", nargs="+", help="remover só estes pacotes")
    s.add_argument("--modo", choices=["desinstalar", "desativar"], default="desinstalar")
    s.add_argument("--aplicar", action="store_true", help="executa de verdade")
    s.add_argument("--sim", action="store_true", help="não pergunta confirmação")

    s = sub.add_parser("reverter", help="reinstala/reativa o que o kit removeu")
    s.add_argument("--tudo", action="store_true")
    s.add_argument("--pacote", nargs="+")

    s = sub.add_parser("otimizar", help="animações, cache e compilação")
    s.add_argument("--animacao", default="0.5", choices=["0", "0.5", "1"])
    s.add_argument("--sem-compilar", action="store_true")
    s.add_argument("--aplicar", action="store_true")
    sub.add_parser("restaurar-otimizacoes", help="volta as animações ao original")
    sub.add_parser("reiniciar", help="reinicia o tablet")

    args = ap.parse_args(argv)
    comandos = {"verificar": cmd_verificar, "varrer": cmd_varrer, "medir": cmd_medir,
                "remover": cmd_remover, "reverter": cmd_reverter, "otimizar": cmd_otimizar,
                "restaurar-otimizacoes": cmd_restaurar_otimizacoes, "reiniciar": cmd_reiniciar}
    try:
        comandos[args.comando](args)
    except ErroKit as e:
        print(f"✘ {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrompido.")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
