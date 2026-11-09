# Tablet sem Obsolescência

Kit para **varrer um tablet Android e tirar o que deixa ele lento sem motivo**: apps de propaganda que se instalam sozinhos, telemetria rodando em segundo plano, limitadores de desempenho e bloatware de fábrica.

- **Sem root.** Usa só o ADB oficial do Google.
- **Tudo é reversível.** Os apps saem só do seu usuário (`pm uninstall --user 0`) e podem voltar com um comando.
- **Simula antes de fazer.** Nada é alterado sem `--aplicar` e sem você digitar `SIM`.
- **Não remove o que é essencial.** A Play Store, os serviços do Google, a tela inicial e outros apps essenciais ficam bloqueados.
- **Funciona em qualquer marca.** O kit detecta o modelo e classifica os apps com um [banco de pacotes](dados/pacotes.json) que a comunidade pode ampliar.
- **Duas versões iguais:** Python (Windows, Linux, Mac) e PowerShell (Windows, sem instalar nada).

> Inspirado na ideia do repositório [cavaleiro-ai/Tirando-defeito-programado-dos-tablets](https://github.com/cavaleiro-ai/Tirando-defeito-programado-dos-tablets). Este projeto é uma reescrita independente, focada só em limpeza e desempenho (sem emuladores).

---

## O que o kit consegue e o que não consegue

| Problema | O kit resolve? |
|---|---|
| Apps de propaganda que reinstalam jogos sozinhos (AppCloud, Aura, ironSource) | ✅ Remove |
| Telemetria e serviços do Facebook pré-instalados | ✅ Remove |
| Bloatware de fábrica e de parceiros | ✅ Remove |
| Limitador de desempenho (ex.: Game Optimizing Service da Samsung) | ⚠️ Remove, se você quiser (o tablet pode esquentar mais) |
| Atualizações que pesam demais para o aparelho antigo | ⚠️ Pode bloquear, mas aí você também perde as correções de segurança |
| Animações lentas, cache acumulado | ✅ Otimiza |
| Bateria gasta (o sistema reduz a CPU para economizar) | 🔎 Detecta e avisa. A solução é trocar a bateria |
| Armazenamento quase cheio | 🔎 Detecta e avisa |
| Processador antigo / pouca RAM | ❌ É hardware. Nenhum software resolve |

---

## Passo a passo

### 1. Prepare o tablet
1. **Configurações > Sobre o tablet > Informações de software**: toque 7 vezes em **Número de compilação** para ativar o modo desenvolvedor.
2. **Configurações > Opções do desenvolvedor**: ligue **Depuração USB**.
3. Conecte o tablet ao computador com um **cabo de dados**. Cabos que só carregam não funcionam.
4. Quando o tablet perguntar, toque em **Permitir depuração USB**.

### 2. Baixe o kit e o ADB
```bash
git clone https://github.com/RobertBorges98/tablet-sem-obsolescencia.git
cd tablet-sem-obsolescencia
```
Para instalar o ADB:
- **Windows:** `powershell -ExecutionPolicy Bypass -File scripts\instalar-adb.ps1`. O script baixa do Google e confere a assinatura digital.
- **Linux:** `sudo apt install adb`
- **Mac:** `brew install android-platform-tools`

### 3. Use o kit

| O que fazer | Python | PowerShell (em `powershell\`) |
|---|---|---|
| Conferir a conexão | `python python/tabletkit.py verificar` | `.\TabletKit.ps1 verificar` |
| **Varredura completa** | `python python/tabletkit.py varrer` | `.\TabletKit.ps1 varrer` |
| Medir antes | `python python/tabletkit.py medir --rotulo antes` | `.\TabletKit.ps1 medir -Rotulo antes` |
| Ver o que seria removido | `python python/tabletkit.py remover` | `.\TabletKit.ps1 remover` |
| Remover os apps "seguros" | `python python/tabletkit.py remover --aplicar` | `.\TabletKit.ps1 remover -Aplicar` |
| Remover só propaganda e telemetria | `... remover --categoria propaganda telemetria --aplicar` | `... remover -Categoria propaganda,telemetria -Aplicar` |
| Remover o limitador de desempenho | `... remover --risco cuidado --categoria limitador --aplicar` | `... remover -Risco cuidado -Categoria limitador -Aplicar` |
| Remover um app específico | `... remover --pacote com.exemplo.app --aplicar` | `... remover -Pacote com.exemplo.app -Aplicar` |
| Desativar em vez de remover | acrescente `--modo desativar` | acrescente `-Modo desativar` |
| Otimizar (animações, cache, compilação) | `... otimizar --aplicar` | `... otimizar -Aplicar` |
| Medir depois (reinicie antes) | `... medir --rotulo depois` | `... medir -Rotulo depois` |
| **Desfazer tudo** | `... reverter --tudo` | `... reverter -Tudo` |
| Voltar as animações | `... restaurar-otimizacoes` | `... restaurar-otimizacoes` |

> Se o PowerShell bloquear o script, rode antes: `Set-ExecutionPolicy -Scope Process Bypass`.

A varredura gera um relatório em `relatorios/<modelo>_<serial>/varredura-<data>.md`. Ele mostra a saúde da RAM, do armazenamento e da bateria, os alertas, os apps classificados por risco, os apps que iniciam sozinhos e os que mais gastam RAM. A pasta `relatorios/` fica fora do git porque tem o serial do seu aparelho.

### Níveis de risco

| Nível | Significado |
|---|---|
| ✅ `seguro` | Pode remover sem efeito colateral. É o padrão do `remover`. |
| ⚠️ `cuidado` | Funciona, mas você perde algum recurso. Leia o motivo antes. |
| 🔎 `verificar` | App de sistema que ainda não está no banco. Pesquise antes de remover e [contribua](CONTRIBUTING.md). |
| ⛔ `perigoso` | Essencial. O kit não deixa remover. |

---

## Aparelhos já varridos

| Aparelho | Android | Processador | Observações |
|---|---|---|---|
| Positivo Vaio TL10 | 13 | Unisoc (ums9230) | Pacotes da Positivo (`com.dr.positivo.preload`, `com.positivo.fota`) e ferramentas de fábrica Unisoc (`com.sprd.*`) catalogados |

Varreu outro modelo? Abra uma issue ou um pull request com os pacotes novos. Envie só os nomes dos pacotes do sistema, **nunca o relatório inteiro**: ele tem o serial do aparelho e a lista dos seus apps.

## Deu problema?

- **Um app sumiu e faz falta:** `reverter --pacote NOME`, ou `reverter --tudo`.
- **O tablet não liga direito (bootloop):** em geral não acontece, porque o kit bloqueia os pacotes essenciais. Se acontecer, uma restauração de fábrica pelo modo recovery traz tudo de volta. Os apps removidos com `--user 0` continuam no sistema.
- **O app voltou depois de uma atualização do sistema:** é normal. Rode `varrer` e `remover` de novo.
- Veja também o [FAQ](docs/FAQ.md).

## Contribua

O banco [`dados/pacotes.json`](dados/pacotes.json) é o coração do projeto. Se você testou a remoção de um pacote no seu tablet, abra um pull request. Veja como em [CONTRIBUTING.md](CONTRIBUTING.md).

## Aviso

Use por sua conta e risco. Os comandos são reversíveis e o kit tem travas de segurança, mas cada fabricante e versão do Android se comporta de um jeito. Faça backup das suas fotos e arquivos antes.

## Licença

[MIT](LICENSE)
