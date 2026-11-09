# Como contribuir

O jeito mais útil de ajudar é **ampliar o banco de pacotes** (`dados/pacotes.json`) com os apps do seu tablet.

## Adicionar ou corrigir um pacote

1. Rode `varrer` no seu tablet e veja a seção **🔎 não catalogados** do relatório.
2. Pesquise o pacote (nome + "uninstall adb" costuma achar respostas) e **teste no seu aparelho**: remova, reinicie e use por alguns dias.
3. Acrescente uma entrada em `pacotes` no `dados/pacotes.json`:

```json
{"pacote": "com.exemplo.app", "nome": "Nome visível", "fabricante": "Marca", "categoria": "bloatware", "risco": "seguro", "motivo": "O que ele faz e o que se perde ao remover."}
```

- **categoria:** `propaganda`, `telemetria`, `bloatware`, `limitador`, `atualizacao` ou `essencial`
- **risco:** `seguro`, `cuidado` ou `perigoso`. Na dúvida, use o mais cauteloso.
- **motivo:** frase curta em português, dizendo o efeito colateral.

4. Abra um pull request informando **modelo do tablet e versão do Android** em que você testou.

## Regras do banco

- Nunca marque como `seguro` algo que você não testou.
- Se remover um pacote quebrou alguma função, ele é no mínimo `cuidado`. Se travou o aparelho, é `perigoso`.
- Mantenha o arquivo como JSON válido. O teste `python -m unittest discover tests` confere isso.

## Código

- `python/tabletkit.py` e `powershell/TabletKit.ps1` devem ter **os mesmos comandos e o mesmo comportamento**. Se mudar um, mude o outro.
- O Python usa só a biblioteca padrão (3.10+).
- Toda ação que altera o tablet precisa: simular por padrão, pedir confirmação, registrar em `acoes.jsonl` e poder ser revertida.
