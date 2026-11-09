# Perguntas frequentes

### Isso é "obsolescência programada" mesmo?
Em parte. Muito da lentidão de tablets antigos vem de coisas que o fabricante e os parceiros põem no aparelho e que **não precisam estar lá**: instaladores de propaganda, telemetria, serviços que iniciam junto com o sistema e limitadores de desempenho. É isso que o kit tira. Outra parte vem do hardware (processador antigo, pouca RAM, bateria gasta), e nenhum software resolve isso. A varredura ajuda a separar uma coisa da outra.

### Preciso de root? Perco a garantia?
Não precisa de root e o bootloader não é desbloqueado. Os comandos usados (`pm uninstall --user 0`, `pm disable-user`) são recursos normais do Android para desenvolvedores.

### Qual a diferença entre remover e desativar?
- **Remover** (`pm uninstall -k --user 0`): o app some para o seu usuário e libera mais recursos. Volta com `reverter`.
- **Desativar** (`pm disable-user`): o app continua instalado, mas não roda. É mais conservador e alguns fabricantes bloqueiam essa opção.

Nos dois casos o APK original continua na partição do sistema, então dá para voltar atrás.

### Devo remover o Game Optimizing Service (GOS) da Samsung?
O GOS limita CPU e GPU em jogos e apps pesados. Sem ele o desempenho melhora, mas o tablet pode esquentar mais e gastar mais bateria. Por isso ele está marcado como `cuidado` e só sai se você pedir (`--risco cuidado --categoria limitador`).

### Devo bloquear as atualizações do sistema?
Normalmente não. Bloquear (`--categoria atualizacao --risco cuidado`) evita que uma versão nova pese demais num aparelho antigo, mas também corta as **correções de segurança**. Só faça isso se o tablet já não recebe atualizações de segurança ou se é usado só para coisas sem dados sensíveis.

### Aparecem janelas de "o app parou" / "o app continua apresentando falhas"
1. Rode `falhas`. O kit lista quais apps fecharam sozinhos, quantas vezes e a causa. Ele lê o registro de falhas que o próprio Android guarda.
2. Se a causa for `ClassNotFoundException`, `NoClassDefFoundError` ou `VerifyError`, o app não consegue carregar o próprio código. Rode `integridade`: ele copia o arquivo de instalação (APK) de cada app para o PC e confere se está corrompido. O `unzip` do Android não confere isso direito, por isso a cópia.
3. Para consertar:
   - **App do sistema** (ex.: Telefone do Google): `reparar --pacote APP --aplicar` volta para a versão de fábrica sem apagar dados. Depois a Play Store baixa a atualização de novo.
   - **App baixado da loja:** se a Play Store oferecer "Atualizar", atualize, porque isso troca o arquivo e mantém os dados. Senão, desinstale e instale de novo. Isso **apaga os dados do app**, então faça backup antes.

Recompilar o app (`cmd package compile`) não resolve: o arquivo de origem está danificado. No Android 13, o ADB nem tem permissão para apagar a compilação.

Se vários apps aparecerem corrompidos sem motivo, rode `integridade` de novo depois de alguns dias. Se surgirem corrompidos novos, a memória do aparelho pode estar com defeito.

### Desativei um app, reiniciei e ele voltou
O Android leva uns 10 segundos para gravar que um app foi ativado ou desativado. Se o tablet reiniciar antes disso, a mudança se perde. Use o comando `reiniciar` do kit, que espera 20 segundos antes de reiniciar. Se usar `adb reboot` direto, espere um pouco antes.

### Animações em 0 ou 0.5?
Com `0.5` o tablet parece mais rápido e ainda dá para ver as transições. Com `0` fica mais rápido ainda, mas alguns apps se comportam de forma estranha. O padrão do kit é `0.5`.

### Os apps voltaram depois de uma atualização
Atualizações grandes do sistema podem reinstalar apps. Rode `varrer` e `remover` de novo.

### Como medir se melhorou?
1. Reinicie o tablet, espere 2 minutos e rode `medir --rotulo antes`.
2. Faça a limpeza e a otimização, reinicie e espere 2 minutos.
3. Rode `medir --rotulo depois`. O kit compara a RAM livre, a quantidade de apps ativos e o tempo para abrir as Configurações.
