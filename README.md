# slidecut

Converte apresentações e documentos para PDF e **corta em capítulos nos slides divisores coloridos** —
aqueles slides de fundo chapado que anunciam um tema novo.

A cor do divisor é **detectada sozinha**: o programa procura a cor forte que se repete ao longo do
arquivo. Não há cor fixa no código, então funciona com qualquer template.

## Instalação

Requisito: [LibreOffice](https://www.libreoffice.org/) instalado (só para entradas que não sejam PDF).

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
```

No Linux/macOS troque `.venv/Scripts/python.exe` por `.venv/bin/python`.

## Uso

```bash
slidecut "aula.pptx"
```

Gera a pasta `aula - cortes/` ao lado do arquivo, com um PDF por capítulo:

```
01 - Conceito.pdf
02 - As Quatro Fases do Direito Processual Civil.pdf
03 - Neoconstitucionalismo.pdf
...
```

Conferir antes de gravar:

```bash
slidecut "aula.pptx" --list
```

### Opções

| Opção | Para que serve |
|---|---|
| `-o`, `--out PASTA` | Pasta de saída (padrão: `<nome> - cortes`) |
| `--list` | Só mostra os cortes detectados, não grava nada |
| `--color #B06E03` | Força a cor do divisor em vez de detectar |
| `--tolerance N` | Quanto a cor pode variar entre páginas (padrão: 45) |
| `--min-coverage F` | Fração mínima da página coberta pela cor (padrão: 0.45) |
| `--ascii` | Nomes de arquivo sem acento |

Variável de ambiente `SLIDECUT_SOFFICE` aponta para o executável do LibreOffice quando ele não está no PATH.

## Interface gráfica

```bash
.venv/Scripts/python.exe -m slidecut.gui
```

Fluxo em duas telas:

1. **Escolher o arquivo.** Se não for PDF, o programa avisa que precisa converter e pede
   confirmação antes de chamar o LibreOffice. O arquivo original nunca é alterado.
2. **Escolher os cortes.** Todas as páginas aparecem como miniaturas. A detecção por cor entra
   apenas como **sugestão inicial** — quem decide é você, marcando e desmarcando páginas.
   Isso cobre o que a cor não pega: slide só com título, divisor com foto de fundo, template
   sem cor chapada.

Cada página marcada abre um capítulo novo e ganha um campo de nome editável, já preenchido com
o texto da própria página. Útil quando o corte cai numa página de conteúdo, cujo texto corrido
daria um nome ruim.

Botões `Usar sugestão por cor` e `Limpar marcas` refazem a seleção inteira de uma vez.

## Gerar o executável (.exe)

```bash
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/pyinstaller.exe --noconfirm --onefile --windowed --name slidecut --paths src entry_gui.py
```

Gera `dist/slidecut.exe`, standalone (não precisa Python instalado na máquina que for rodar —
só o LibreOffice, e apenas se for converter algo que não seja PDF).

## Formatos aceitos

| Categoria | Extensões |
|---|---|
| Slides | `.pptx` `.ppt` `.odp` `.key` `.pps` `.ppsx` `.fodp` `.otp` |
| Texto | `.docx` `.doc` `.odt` `.rtf` `.txt` `.fodt` `.ott` `.pages` |
| Planilha | `.xlsx` `.xls` `.ods` `.csv` `.numbers` |
| PDF | `.pdf` (usado direto, sem conversão) |

## Como a detecção funciona

1. Cada página é renderizada em baixa resolução e reduzida à sua **cor dominante**.
2. Uma página é candidata a divisora se essa cor cobre boa parte dela e não é um fundo claro neutro —
   ou seja, é saturada (colorida) ou bem escura.
3. As candidatas são agrupadas por proximidade de cor. O grupo que **mais se repete** (mínimo 2 páginas)
   é a cor divisora.
4. Cada divisor abre um capítulo, que vai até o divisor seguinte. O título vem do texto do próprio
   slide, descartando a linha de crédito do professor.

Páginas antes do primeiro divisor viram um capítulo `Abertura`.

## Desenvolvimento

```bash
.venv/Scripts/python.exe -m pytest --cov=slidecut
```

Testes lentos (`-m slow`) sobem o LibreOffice de verdade e são pulados se ele não estiver instalado.

| Módulo | Responsabilidade |
|---|---|
| `convert.py` | Entrada → PDF via LibreOffice headless |
| `analyze.py` | Cor dominante por página e detecção dos divisores |
| `titles.py` | Título do slide → nome de arquivo válido |
| `split.py` | Intervalos de páginas → PDFs de saída |
| `preview.py` | Miniatura e legenda de cada página |
| `core.py` | Fluxo compartilhado: automático (`process`) e manual (`prepare` + `cut_at`) |
| `cli.py` | Argumentos, relatório e código de saída |
| `gui.py` | Janela: escolha do arquivo e seleção manual dos cortes |

A CLI continua 100% automática (útil em lote); o modo manual existe só na interface gráfica.
