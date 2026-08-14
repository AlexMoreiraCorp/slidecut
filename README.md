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

Selecionar arquivo (PDF ou slide/documento/planilha) → conferir/ajustar pasta de saída e cor
opcional → "Pré-visualizar" (só mostra os cortes) ou "Cortar" (grava).

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
| `cli.py` | Argumentos, relatório e código de saída |
