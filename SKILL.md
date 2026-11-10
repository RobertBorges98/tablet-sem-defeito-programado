---
name: tablet-sem-defeito-programado
description: Varre e otimiza tablets e celulares Android via ADB, sem root e de forma reversível. Remove bloatware, propaganda, telemetria e limitadores de desempenho, diagnostica apps que fecham sozinhos ("o app parou"), encontra APKs corrompidos e mede o antes e o depois. Use quando a pessoa pedir para deixar um tablet/celular Android mais rápido, tirar apps de fábrica, "obsolescência programada", consertar pop-ups de falha de app, ou conectar um aparelho por ADB.
---

# Tablet sem Obsolescência

Kit em `python/tabletkit.py` (Python 3.10+, só biblioteca padrão) e `powershell/TabletKit.ps1` (Windows PowerShell 5.1+). As duas versões têm os mesmos comandos e leem o mesmo banco de pacotes (`dados/pacotes.json`). Responda à pessoa no idioma dela. O kit fala português.

Todos os caminhos abaixo são relativos à pasta desta skill. Rode os comandos a partir dela.

## Regras de segurança (obrigatórias)

1. **Simule antes de aplicar.** `remover`, `otimizar` e `reparar` só alteram algo com `--aplicar`. Mostre a simulação à pessoa e **peça confirmação** antes de rodar com `--aplicar`.
2. **Nunca force a remoção de um pacote `perigoso`.** O kit bloqueia, e não tente contornar o bloqueio com `adb shell pm` direto.
3. **Pergunte o que a pessoa usa** antes de remover apps com que ela interage: streaming, navegador, e-mail, câmera, galeria, videochamada. "Seguro" quer dizer que o sistema não quebra, não que a pessoa não usa.
4. **Com aparelho de criança ou controle parental** (a varredura mostra o alerta 👶 Family Link), não remova nem desative o Bem-estar digital (`com.google.android.apps.wellbeing`), a supervisão (`com.google.android.gms.supervision`), o `familylinkhelper` e, se a criança usa, o Espaço Kids. Priorize tirar apps que coletam dados ou mostram propaganda.
5. **Para apps de sistema ou de fábrica ainda não testados,** use `--modo desativar`. É mais conservador que desinstalar.
6. **Nunca apague dados de um app** (`pm clear`, desinstalar sem `--user 0`) sem a pessoa pedir explicitamente. No caso de WhatsApp e similares, confira antes se há backup.
7. **A pasta `relatorios/` tem o serial do aparelho e a lista de apps da pessoa.** Não publique, não cole em issues e não envie para fora do computador.
8. Tudo o que o kit faz é reversível: `reverter --tudo`, `restaurar-otimizacoes`.

## Preparação

- O ADB é procurado nesta ordem: variável `TABLETKIT_ADB`, o `adb` no PATH e `platform-tools/` da skill. No Windows, sem ADB, rode `powershell -ExecutionPolicy Bypass -File scripts/instalar-adb.ps1`. Ele baixa do Google e confere a assinatura. No Linux: `sudo apt install adb`. No Mac: `brew install android-platform-tools`.
- No aparelho: Opções do desenvolvedor > Depuração USB ligada, cabo de dados, e aceitar "Permitir depuração USB".
- Com mais de um aparelho conectado, passe `--serial SERIAL` **antes** do subcomando: `python python/tabletkit.py --serial X varrer`.

## Fluxo recomendado

1. `python python/tabletkit.py verificar`: confirma a conexão e mostra o modelo.
2. `python python/tabletkit.py varrer`: gera `relatorios/<modelo>_<serial>/varredura-*.md`. Leia o relatório e resuma para a pessoa:
   - saúde (RAM, armazenamento, bateria, patch de segurança) e alertas;
   - apps ✅ seguros e ⚠️ com cuidado;
   - apps de terceiros e do sistema que iniciam sozinhos;
   - os que mais gastam RAM.
3. `python python/tabletkit.py falhas`: apps que fecham sozinhos e a causa. Se houver `ClassNotFoundException`, `NoClassDefFoundError` ou `VerifyError`, rode `integridade`.
4. Investigue os 🔎 **não catalogados** antes de mexer neles: `adb shell dumpsys package PACOTE` (permissões, `codePath`, `firstInstallTime`) e `adb shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.LAUNCHER PACOTE`. Desconfie de apps de fábrica com localização, uso de apps ou `RECEIVE_BOOT_COMPLETED` concedidos sem pedir.
5. Proponha um plano em tabela (remover, desativar, manter e otimizar), com o motivo de cada um. Pergunte o que a pessoa usa.
6. Se a pessoa quiser números, meça o **antes** de forma justa: `reiniciar`, espere o aparelho ligar mais **5 a 10 minutos** e rode `medir --rotulo antes`.
7. Aplique o que foi aprovado:
   - `remover --pacote A B --aplicar` remove do usuário 0, e `remover --pacote A B --modo desativar --aplicar` desativa;
   - `otimizar --aplicar` (animações em 0,5, limpeza de cache e compilação; use `--sem-compilar` se tiver pressa).
8. `reiniciar`, espere o mesmo tempo e rode `medir --rotulo depois`. O kit compara com a última medição "antes". Confira com `adb shell pm list packages -d` se o que foi desativado **continuou desativado depois do boot**.
9. Relate com honestidade. Ganho pequeno também é resultado. Separe o efeito das animações do efeito das remoções, e diga quando a diferença está dentro do ruído.

Na versão PowerShell, os mesmos comandos ficam assim: `.\powershell\TabletKit.ps1 varrer`, `-Pacote a,b`, `-Aplicar`, `-Modo desativar`, `-Rotulo antes`.

## Referência de comandos

| Comando | O que faz |
|---|---|
| `verificar` | Confere a conexão e mostra o modelo e o Android |
| `varrer` | Diagnóstico completo e relatório em Markdown/JSON, além de um backup da lista de apps |
| `medir [--rotulo antes\|depois]` | RAM livre, apps ativos e tempo de abertura das Configurações (média de 3 vezes) |
| `remover [--risco seguro\|cuidado] [--categoria ...] [--pacote ...] [--modo desinstalar\|desativar] [--aplicar] [--sim]` | Simula por padrão e bloqueia os essenciais |
| `reverter [--tudo \| --pacote ...]` | Reinstala ou reativa, conferindo o estado real |
| `otimizar [--animacao 0\|0.5\|1] [--sem-compilar] [--aplicar]` | Animações, limpeza de cache e `bg-dexopt-job` |
| `restaurar-otimizacoes` | Volta as animações ao original |
| `reiniciar` | Espera 20 s (para o Android gravar as mudanças) e reinicia |
| `falhas` | Agrupa as falhas do DropBox do Android por app e causa |
| `integridade [--pacote ...]` | Copia os APKs de `/data/app` para o PC e confere o CRC |
| `reparar --pacote ... [--aplicar]` | App do sistema com atualização corrompida: volta para a versão de fábrica sem apagar dados |

## Armadilhas descobertas em aparelhos reais

- **O Android grava ativar/desativar app com cerca de 10 s de atraso.** `adb reboot` logo depois perde a mudança. Use sempre `reiniciar` do kit, que espera 20 s.
- **`pm disable-user --user 0` só é desfeito com `pm enable --user 0`.** O `reverter` já faz isso e confere se o app aparece em `pm list packages -e`.
- **Medir RAM logo após o boot engana.** Os apps que iniciam sozinhos ainda estão carregando. Espere de 5 a 10 minutos, e compare sempre medições feitas nas mesmas condições.
- **"O app parou" a cada boot** costuma ser APK corrompido, não bloatware. Recompilar (`cmd package compile -f`) falha, e o `--reset` é negado ao shell no Android 13. O `unzip` do aparelho **não confere CRC**, por isso o `integridade` copia o APK para o PC. Para app do sistema, use `reparar`. Para app da loja, atualize pela Play Store (mantém os dados) ou reinstale (apaga os dados: faça backup antes).
- **Vários APKs corrompidos sem motivo** podem indicar defeito na memória. Recomende rodar `integridade` de novo dias depois.
- **Overlays (`*.overlay`, `auto_generated_rro`, temas de ícone) não rodam nem gastam RAM.** O relatório os esconde. Não perca tempo com eles.
- **Android Go** (`ro.config.low_ram=true`) e aparelhos com 2 GB ou menos de RAM: o que mais ajuda é desativar o que inicia sozinho (testes de fábrica, telemetria, assistente) e baixar as animações.
- **No PowerShell chamado com `powershell -File`,** `-Pacote a,b` chega como um texto só. O kit já separa as vírgulas.

## Contribuir com o banco

Depois de testar um pacote novo em um aparelho, acrescente-o a `dados/pacotes.json` (veja `CONTRIBUTING.md`). Na dúvida, use o risco mais cauteloso. Pacotes internos do sistema vão em `componentes_sistema`. Rode `python -m unittest discover tests` antes de enviar.
