# slidecut

Converte apresentações e documentos para PDF e **corta em capítulos nos slides divisores coloridos** —
aqueles slides de fundo chapado que anunciam um tema novo.

A cor do divisor é **detectada sozinha**: o programa procura a cor forte que se repete ao longo do
arquivo. Não há cor fixa no código, então funciona com qualquer template.

## Instalação (usuário final)

Rode `slidecut-setup-X.Y.Z.exe`. Ele instala o programa, cria o atalho na área de trabalho
(opcional) e no menu iniciar, e registra o desinstalador no Painel de Controle.

### Conversão de slides e documentos

Cortar um PDF não exige nada além do programa. Converter apresentações e documentos exige um
conversor, e o slidecut usa o que a máquina já tiver:

1. **Microsoft Office**, se instalado. É o caminho preferido: quem renderiza é o próprio
   PowerPoint/Word/Excel, então o PDF sai idêntico ao que o autor via, e é mais rápido
   (~2s contra ~5s do LibreOffice num arquivo pequeno).
2. **LibreOffice**, quando não há Office — e também quando o Office falha.

**Os dois se completam, e vale ter ambos.** Existem arquivos que o PowerPoint abre e desenha na
tela, mas se recusa a exportar: falham tanto `SaveAs` para PDF quanto `SaveCopyAs` para `.pptx`.
Nesses casos o LibreOffice é o único que dá conta. Por isso o instalador oferece baixá-lo
(~350 MB, marcado por padrão) para quem ainda não o tem, mesmo em máquinas com Office —
conferindo o SHA-256 publicado pela The Document Foundation antes de executar.

Quem já tem LibreOffice não vê essa opção, e ela pode ser desmarcada por quem não quiser.

O programa nunca fecha um Office que já estava aberto: se você estiver com o PowerPoint em uso, ele
se conecta à sua sessão para exportar e a deixa exatamente como estava.

## Instalação (desenvolvimento)

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

1. **Escolher o arquivo** — arrastando para a janela ou pelo seletor. Se não for PDF, o programa
   diz qual conversor vai usar e pede confirmação. O arquivo original nunca é alterado.
2. **Escolher os cortes.** Todas as páginas aparecem como miniaturas. A detecção por cor entra
   apenas como **sugestão inicial** — quem decide é você, marcando e desmarcando páginas.
   Isso cobre o que a cor não pega: slide só com título, divisor com foto de fundo, template
   sem cor chapada.

Cada página marcada abre um capítulo novo e ganha um campo de nome editável, já preenchido com
o texto da própria página. Útil quando o corte cai numa página de conteúdo, cujo texto corrido
daria um nome ruim.

Botões `Usar sugestão por cor` e `Limpar marcas` refazem a seleção inteira de uma vez.

## Gerar o executável e o instalador

```powershell
.\tools\build.ps1
```

Gera o ícone, roda os testes, empacota `dist/slidecut.exe` (standalone — não precisa Python na
máquina de destino) e compila `dist/slidecut-setup-X.Y.Z.exe`.

Requer [Inno Setup 6](https://jrsoftware.org/isdl.php) para a etapa do instalador; sem ele o
script avisa e entrega só o executável.

O ícone é desenhado por código em [`tools/make_icon.py`](tools/make_icon.py) e gravado em
`src/slidecut/assets/` — dentro do pacote, para que o mesmo caminho funcione rodando do fonte e
dentro do executável congelado.

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
| `convert.py` | Entrada → PDF: escolhe o conversor e cai para o seguinte se falhar |
| `office.py` | Conversão pelo Microsoft Office instalado (automação COM) |
| `analyze.py` | Cor dominante por página e detecção dos divisores |
| `titles.py` | Título do slide → nome de arquivo válido |
| `split.py` | Intervalos de páginas → PDFs de saída |
| `preview.py` | Miniatura e legenda de cada página |
| `core.py` | Fluxo compartilhado: automático (`process`) e manual (`prepare` + `cut_at`) |
| `cli.py` | Argumentos, relatório e código de saída |
| `gui.py` | Janela: escolha do arquivo e seleção manual dos cortes |
| `resources.py` | Localiza o ícone, no fonte e no executável congelado |
| `theme.py` | Cores, fontes e estilos ttk da janela |

A CLI continua 100% automática (útil em lote); o modo manual existe só na interface gráfica.

## Sistema visual

A janela segue uma regra só: **laranja quer dizer "cortar aqui", e nada mais.** Nenhum botão
decorativo, nenhum destaque gratuito usa laranja — assim a interface fala a mesma língua do
conteúdo, já que o programa procura justamente slides divisores coloridos. O único botão
preenchido de laranja é o que gera os cortes.

O resto é azul-tinta no cabeçalho e papel cinza-frio na área de trabalho, como uma mesa de luz
onde se inspecionam páginas. Tipografia: Bahnschrift (DIN, sinalização técnica) nos rótulos,
Segoe UI no texto, Cascadia Mono nos números de página. Os tokens estão em `theme.py`.

Na folha de contato, cada corte marcado abre uma faixa de capítulo e as páginas se reagrupam
embaixo dela — dá para ver os arquivos se formando antes de gerar. O rearranjo é adiado 120 ms
após o último clique e leva cerca de 0,3 s numa folha de 145 páginas; marcar várias páginas
seguidas não custa nada.

## Vários arquivos de uma vez (lote)

Botão "Processar vários arquivos" no cabeçalho da janela. Aceita a mesma lista de formatos de
sempre, dois modos:

- **Cortar cada arquivo em capítulos** — cada entrada vai para sua própria subpasta dentro da
  pasta de saída escolhida, nomeada com o nome do arquivo original.
- **Só converter para PDF** — todos os arquivos convertidos direto na pasta de saída, sem
  subpasta. Duas entradas que gerariam o mesmo nome de saída são detectadas e a segunda é
  recusada, em vez de sobrescrever a primeira em silêncio.

Um arquivo com problema (corrompido, sem divisor, formato que nenhum conversor abre) não
interrompe o lote — fica registrado como falha e os demais continuam. Ao final, um resumo lista
quantos deram certo e, para cada um que falhou, o motivo.

## Sobre converter PDF em slides

Testado e não é oferecido. O PowerPoint não abre PDF diretamente (falha na automação). O único
caminho que funciona é renderizar cada página como imagem e colar um slide por imagem — mas o
texto deixa de ser editável, vira uma foto do PDF dentro do slide. Preferimos não oferecer uma
conversão que decepciona quem espera texto editável.
