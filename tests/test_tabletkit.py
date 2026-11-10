import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ / "python"))
import tabletkit  # noqa: E402


class TestBanco(unittest.TestCase):
    def setUp(self):
        self.dados = json.loads((RAIZ / "dados" / "pacotes.json").read_text(encoding="utf-8"))

    def test_campos_validos(self):
        cats = set(self.dados["legenda_categoria"])
        riscos = set(self.dados["legenda_risco"])
        vistos = set()
        for p in self.dados["pacotes"]:
            for campo in ("pacote", "nome", "categoria", "risco", "motivo"):
                self.assertTrue(p.get(campo), f"{p} sem {campo}")
            self.assertIn(p["categoria"], cats, p["pacote"])
            self.assertIn(p["risco"], riscos, p["pacote"])
            self.assertNotIn(p["pacote"], vistos, f"duplicado: {p['pacote']}")
            vistos.add(p["pacote"])

    def test_essenciais_sao_perigosos(self):
        for p in self.dados["pacotes"]:
            if p["categoria"] == "essencial":
                self.assertEqual(p["risco"], "perigoso", p["pacote"])

    def test_classificacao(self):
        b = tabletkit.Banco()
        self.assertEqual(b.classificar("com.android.vending")["risco"], "perigoso")
        self.assertEqual(b.classificar("com.android.providers.media")["risco"], "perigoso")
        self.assertEqual(b.classificar("com.dti.outro")["categoria"], "suspeito")
        self.assertEqual(b.classificar("com.qualquer.coisa")["risco"], "verificar")
        self.assertEqual(b.classificar("com.android.vpndialogs")["risco"], "perigoso")

    def test_componentes_nao_duplicam_pacotes(self):
        comp = set(self.dados["componentes_sistema"]["pacotes"])
        self.assertFalse(comp & {p["pacote"] for p in self.dados["pacotes"]})


class TestComAdbFalso(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        if os.name == "nt":
            adb = tmp / "adb.bat"
            adb.write_text(f'@"{sys.executable}" "{AQUI / "adb_falso.py"}" %*\n')
        else:
            adb = tmp / "adb"
            adb.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{AQUI / "adb_falso.py"}" "$@"\n')
            adb.chmod(0o755)
        os.environ["TABLETKIT_ADB"] = str(adb)
        os.environ["ADB_FALSO_ESTADO"] = str(tmp / "estado.json")
        self._rel = tabletkit.RELATORIOS
        tabletkit.ESPERA_GRAVAR_S = 0
        tabletkit.RELATORIOS = tmp / "relatorios"

    def tearDown(self):
        tabletkit.RELATORIOS = self._rel
        self.tmp.cleanup()

    def rodar(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = tabletkit.main(list(args))
        return rc, buf.getvalue()

    def estado(self):
        return json.loads(Path(os.environ["ADB_FALSO_ESTADO"]).read_text())["instalado"]

    def test_varrer_gera_relatorio(self):
        rc, saida = self.rodar("varrer")
        self.assertEqual(rc, 0, saida)
        mds = list(tabletkit.RELATORIOS.rglob("varredura-*.md"))
        self.assertEqual(len(mds), 1)
        texto = mds[0].read_text(encoding="utf-8")
        self.assertIn("SM-X200", texto)
        self.assertIn("com.dti.samsung", texto)
        self.assertIn("Game Optimizing Service ativo", texto)
        self.assertIn("Armazenamento quase cheio", texto)
        antes_boot, boot = texto.split("## Apps de terceiros que iniciam")
        self.assertNotIn("com.whatsapp", antes_boot)
        self.assertIn("com.whatsapp", boot.split("## Apps do sistema")[0])
        self.assertNotIn("theme.icon.pebble", texto)
        self.assertIn("1 overlays ocultos", texto)
        self.assertIn("1 apps de propaganda/telemetria", texto)

    def test_oculto(self):
        b = tabletkit.Banco()
        self.assertTrue(b.oculto("com.android.systemui.revo.overlay"))
        self.assertTrue(b.oculto("com.android.wifi.resources"))
        self.assertFalse(b.oculto("com.dr.positivo.preload"))

    def test_remover_simula_por_padrao(self):
        rc, saida = self.rodar("remover")
        self.assertEqual(rc, 0)
        self.assertIn("SIMULAÇÃO", saida)
        self.assertTrue(self.estado()["com.dti.samsung"])

    def test_remover_e_reverter(self):
        self.rodar("remover", "--aplicar", "--sim")
        e = self.estado()
        self.assertFalse(e["com.dti.samsung"])
        self.assertTrue(e["com.samsung.android.game.gos"], "cuidado não sai no padrão")
        self.assertTrue(e["com.android.vending"])
        self.rodar("reverter", "--tudo")
        self.assertTrue(self.estado()["com.dti.samsung"])

    def test_essencial_bloqueado(self):
        _, saida = self.rodar("remover", "--pacote", "com.android.vending", "--aplicar", "--sim")
        self.assertIn("bloqueado", saida)
        self.assertTrue(self.estado()["com.android.vending"])

    def test_desativar(self):
        self.rodar("remover", "--pacote", "com.samsung.android.game.gos", "--modo", "desativar", "--aplicar", "--sim")
        self.assertEqual(self.estado()["com.samsung.android.game.gos"], "off")
        self.rodar("reverter", "--pacote", "com.samsung.android.game.gos")
        self.assertTrue(self.estado()["com.samsung.android.game.gos"])

    def test_reverter_usa_estado_real(self):
        """Reverter de novo um app que voltou a ficar desativado (o histórico diz 'já revertido')."""
        gos = "com.samsung.android.game.gos"
        self.rodar("remover", "--pacote", gos, "--modo", "desativar", "--aplicar", "--sim")
        self.rodar("reverter", "--tudo")
        caminho = Path(os.environ["ADB_FALSO_ESTADO"])
        e = json.loads(caminho.read_text()); e["instalado"][gos] = "off"; caminho.write_text(json.dumps(e))
        _, saida = self.rodar("reverter", "--pacote", gos)
        self.assertIn("✔", saida)
        self.assertTrue(self.estado()[gos])

    def test_falhas_e_reparar(self):
        _, saida = self.rodar("falhas")
        self.assertIn("com.google.android.dialer", saida)
        self.assertIn("NoClassDefFoundError", saida)
        sugestao = re.search(r"integridade --pacote (.+)", saida).group(1).split()
        self.assertEqual(sorted(sugestao), ["com.google.android.dialer", "com.truecaller"])

    def test_integridade_e_reparar(self):
        _, saida = self.rodar("integridade")
        self.assertIn("Conferindo 3 arquivos", saida)
        self.assertIn("com.truecaller — base.apk: CRC inválido em classes.dex", saida)
        self.assertIn("com.google.android.dialer — base.apk: CRC inválido", saida)
        self.assertNotIn("com.whatsapp —", saida)
        self.assertIn("reparar --pacote com.google.android.dialer --aplicar", saida)   # do sistema
        self.assertIn("• com.truecaller", saida)                                       # baixado
        _, saida = self.rodar("reparar", "--pacote", "com.google.android.dialer", "com.truecaller")
        self.assertIn("SIMULAÇÃO", saida)
        self.assertIn("com.truecaller: app baixado da loja", saida)
        self.rodar("reparar", "--pacote", "com.google.android.dialer", "com.truecaller", "--aplicar")
        e = json.loads(Path(os.environ["ADB_FALSO_ESTADO"]).read_text())
        self.assertEqual(e.get("reparados"), ["com.google.android.dialer"])
        _, saida = self.rodar("integridade", "--pacote", "com.google.android.dialer")
        self.assertIn("Conferindo 0 arquivos", saida)

    def test_otimizar_e_restaurar(self):
        self.rodar("otimizar", "--aplicar", "--sem-compilar")
        self.rodar("restaurar-otimizacoes")
        estado = json.loads(Path(os.environ["ADB_FALSO_ESTADO"]).read_text())
        self.assertEqual(estado["anim"], "1.0")

    def test_medir(self):
        self.rodar("medir", "--rotulo", "depois")
        rc, saida = self.rodar("medir", "--rotulo", "antes")
        self.assertEqual(rc, 0)
        self.assertIn("850 ms", saida)
        self.assertNotIn("Comparado", saida)
        _, saida = self.rodar("medir", "--rotulo", "depois")
        self.assertIn("medição 'antes'", saida)


class TestSkill(unittest.TestCase):
    def test_frontmatter_do_skill(self):
        texto = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
        m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", texto, re.S)
        self.assertTrue(m, "SKILL.md precisa começar com frontmatter YAML")
        campos = dict(linha.split(":", 1) for linha in m.group(1).splitlines() if ":" in linha)
        self.assertEqual(campos.get("name", "").strip(), "tablet-sem-defeito-programado")
        descricao = campos.get("description", "").strip()
        self.assertTrue(20 < len(descricao) <= 1024, "description deve ter até 1024 caracteres")

    def test_comandos_citados_existem(self):
        texto = (RAIZ / "SKILL.md").read_text(encoding="utf-8")
        ajuda = io.StringIO()
        with redirect_stdout(ajuda), self.assertRaises(SystemExit):
            tabletkit.main(["--help"])
        for cmd in re.findall(r"tabletkit\.py (?:--serial \S+ )?([a-z-]+)", texto):
            self.assertIn(cmd, ajuda.getvalue(), f"SKILL.md cita comando inexistente: {cmd}")


if __name__ == "__main__":
    unittest.main()
