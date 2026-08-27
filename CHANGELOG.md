# Notas de atualização

## 0.10.9 — 2026-08-27

- A pasta com os arquivos gerados agora **abre sozinha** quando o corte termina — o modo
  "converter" já fazia isso, o corte não.
- Corrigido o texto **"Cortar em cortes"**, que sobrou da troca de "capítulo" por "corte" na
  0.10.4. Agora é só **"Cortar"** (e "Cortar cada arquivo", no modo de vários arquivos).

## 0.10.8 — 2026-08-27

### Verificação de atualização confiável para o time inteiro
- A consulta anterior usava a API do GitHub, que limita **60 consultas por hora por endereço de
  internet**. Como o time acessa pelo mesmo endereço da empresa, a cota estourava e *ninguém*
  mais recebia aviso de versão nova. Agora a verificação usa a página de lançamentos, que não
  tem essa cota — testado com a cota da API já esgotada, e funcionou normalmente.

## 0.10.7 — 2026-08-27

### Verificação de atualização mais confiável
- A checagem de versão nova passou a consultar a lista oficial de lançamentos do GitHub, em vez
  de ler o código-fonte do projeto. Dois problemas resolvidos: a leitura anterior vinha de um
  endereço com cache de até 5 minutos (o aviso demorava a aparecer), e podia anunciar uma versão
  cujo instalador ainda não tinha sido publicado — o download automático falharia. Agora só é
  anunciada versão que já está pronta para baixar.

## 0.10.6 — 2026-08-27

### Desempenho e fluidez
- Corrigido o **rastro/fantasma ao rolar** a folha de páginas. A causa real: cada página marcada
  criava um campo de texto nativo do Windows dentro da área rolável — com 360 cortes marcados
  eram 360 controles sendo arrastados a cada giro da roda do mouse. Agora só a página aberta no
  painel lateral tem campo editável; as demais mostram o nome como texto simples. O nome
  continua editável: basta clicar na página.
- Menos widgets por página, o que também deixa a abertura de documentos grandes mais leve.

### Animação de espera
- Operações que demoram (aplicar o **slide matriz**, **gerar os cortes**) agora mostram uma
  animação de espera cobrindo a tela, com o texto do que está acontecendo. Antes a janela ficava
  parada, sem indicar se era espera ou travamento.
- Aplicar o slide matriz passou a rodar fora da thread da janela — a tela não congela mais
  enquanto a cor é lida.

### Numerar
- A opção **"numerar (01, 02...)"** agora vem **desmarcada por padrão** e só muda quando o
  usuário clica nela — antes se ligava e desligava sozinha conforme o prefixo era digitado.
- Texto e caixinha com muito mais contraste: antes quase não se percebia que a opção existia.

## 0.10.5 — 2026-08-27

### Atualização automática
- O aviso de "nova versão disponível" agora oferece baixar e instalar sozinho: clicar pergunta
  se quer baixar e instalar agora (o app fecha para concluir) ou abrir a página de download no
  navegador. Nada roda sem essa confirmação.
- O instalador baixado é conferido contra um checksum SHA-256 publicado junto do release antes
  de rodar — se não bater, o app recusa executar e explica o motivo, sem deixar arquivo nenhum
  no disco.
- Falha no download (sem internet, checksum não bate) mostra o motivo e deixa o aviso ali para
  tentar de novo — nunca trava nem esconde o problema.
- A partir desta versão, cada lançamento publica o instalador como *release* no GitHub
  (`slidecut-setup-X.Y.Z.exe` + `.sha256`), que é de onde a atualização automática baixa.

## 0.10.4 — 2026-08-27

### Desempenho
- Corrigido travamento ao usar **"Usar como slide matriz"** em documentos grandes (300+
  páginas). A troca de matriz disparava uma nova varredura de cor de todas as páginas do zero,
  na mesma thread da janela — travava o aplicativo inteiro até terminar. Agora reaproveita as
  cores já calculadas na abertura do arquivo; a troca de matriz é instantânea.

### Terminologia
- "Capítulo" trocado por **"corte"** em toda a tela: rótulos, faixas da grade
  ("CORTE 01", "CORTE 02"...), mensagens de aviso e texto de progresso.

### Versão visível e verificação de atualização
- O número da versão instalada aparece agora no título da janela e no cabeçalho
  (ex.: `v0.10.4`), para saber de relance se está desatualizado.
- O aplicativo verifica em segundo plano, ao abrir, se há uma versão mais nova publicada no
  GitHub. Quando há, aparece um aviso discreto no cabeçalho — clicar abre a página de downloads
  no navegador. Nunca baixa nem instala nada sozinho, e uma checagem que falha (sem internet,
  GitHub fora do ar) não afeta o uso normal do programa.
- O repositório do projeto passou a ser público no GitHub (sem código sensível), o que permite
  essa verificação sem exigir login.

## 0.10.3 — 2026-08-27

### Fluidez
- Corrigido rastro visível ao rolar a folha de páginas com a roda do mouse. O canvas não tinha
  um passo de rolagem fixo (`yscrollincrement`); sem ele, o Windows rolava em frações de pixel
  a cada notch, e cada blit parcial deixava sujeira na tela — mais visível ainda com a janela
  DPI-aware da 0.10.1, onde a escala não é um número inteiro. Agora a rolagem se move em blocos
  de pixel inteiro, sem rastro.

## 0.10.2 — 2026-08-27

### Visual
- Paleta trocada de laranja para dourado escuro (mais vivo): botão principal, marca de "corta
  aqui", detalhes de destaque em toda a aplicação.
- O nome do arquivo escolhido ("Selecionado: nome.pptx") passou a aparecer em dourado escuro e
  negrito — antes usava a mesma cor neutra do resto do texto e passava despercebido ao arrastar
  um arquivo para a janela.

## 0.10.1 — 2026-08-27

### Numeração opcional
- A numeração automática (`01 -`, `02 -`...) continua existindo como antes, mas o **padrão
  mudou**: assim que um prefixo ou sufixo é preenchido, o número deixa de vir por padrão — o
  nome já tem uma etiqueta própria e o número costuma sobrar.
- Novo check **"numerar (01, 02...)"** ao lado dos campos Antes/Depois — na tela de seleção e
  no lote — para religar a numeração quando o usuário quiser as duas coisas juntas. Uma vez
  tocado à mão, o check para de mudar sozinho: a escolha do usuário passa a valer sobre o padrão
  automático.

### Nitidez
- Corrigida a causa raiz do aplicativo aparecer borrado/"baixa resolução": o processo não se
  declarava compatível com a escala de DPI do Windows, então o sistema desenhava a janela a
  96 DPI e esticava o resultado por bitmap para bater com a escala do monitor (125%, 150%...).
  Agora o processo é marcado como DPI-aware por monitor antes de a janela existir, e a escala do
  Tk é ajustada para a DPI real assim que a janela é criada. Texto e ícones saem nítidos em
  qualquer escala do Windows.

### Compatibilidade com tamanhos de tela
- O tamanho inicial da janela deixou de ser fixo (1320×860) e passou a se ajustar à tela
  disponível: encolhe para caber em notebooks menores (ex. 1366×768 com barra de tarefas) sem
  nunca ficar menor que o mínimo utilizável, e centraliza automaticamente.

## 0.10.0 — 2026-08-27

### Nomes dos arquivos
- Novos campos **Antes** e **Depois** na tela de seleção e no lote: o texto digitado entra em
  todos os arquivos gerados, inclusive nos renomeados à mão.
- Cada página marcada agora mostra, abaixo do campo de nome, o **nome exato** que o arquivo vai
  receber — já com número, prefixo e sufixo aplicados.

### Slide matriz
- Em decks com mais de um tom forte, a detecção automática escolhe o que mais se repete — nem
  sempre o divisor certo. Agora dá para abrir o slide que você reconhece como modelo e usar
  **"Usar como slide matriz"**: a cor dele passa a definir o corte do documento inteiro.
- O painel de inspeção mostra a cor lida de cada página (hexadecimal + amostra), para comparar
  antes de decidir.

### Páginas fora do corte
- Novo check **"entra no corte"** em cada página, ligado por padrão. Desmarcar tira a página do
  arquivo gerado sem tocar no documento de origem — ela continua lá.

### Tela de seleção
- **Ver** e **cortar** viraram ações diferentes: um clique na miniatura abre a página no painel
  lateral; dois cliques ampliam mais. A marca de corte ganhou faixa própria com texto
  (`marcar corte aqui` / `CORTA AQUI`), em vez do clique-em-qualquer-canto de antes, que ligava
  cortes sem querer e não dizia como desfazer.
- Painel de inspeção encaixado ao lado da grade (não uma janela separada) — dá para comparar a
  página ampliada com as miniaturas ao mesmo tempo.
- Botão **"← Voltar ao início"** no rodapé.

### Visual
- Botões de cantos redondos em toda a aplicação.
- **"✕ Limpar marcações"** agora em vermelho — ação que desfaz trabalho fica visualmente distinta.
- Paleta ampliada com cor por significado: azul = página em inspeção, roxo = slide matriz,
  verde = entra no corte, vermelho = desfazer. Laranja segue reservado só para "corta aqui".
- Fonte principal passou para Segoe UI Variable (com reserva para Segoe UI).

### Correções (herdadas de 0.9.1, incluídas nesta build)
- Conversão tenta LibreOffice primeiro quando instalado; Microsoft Office vira reserva.
- Corrigido erro `[WinError 5] Acesso negado` esporádico ao agrupar páginas por folha (retry
  automático).
- Tela de lote: botão "Voltar", seleção de arquivos com contraste visível, contagem de
  selecionados no rodapé.

### Testes
- Nova suíte `tests/test_gui_smoke.py` sobe a janela de verdade e testa a fiação entre widgets.
- Cobertura total: 54% → 87%.

---

## 0.9.1 — 2026-08-27

- `convert.to_pdf` tenta LibreOffice primeiro quando instalado; Office vira reserva.
- Corrigido `[WinError 5]` passageiro no agrupamento de páginas (antivírus/indexador segurando
  o arquivo recém-escrito) — causa real do erro relatado pelo usuário.
- Tela de lote: botão "Voltar" no rodapé, seleção com contraste alto, contador de selecionados.
- Removida da tela inicial a mensagem "será convertido pelo Office/LibreOffice".

## 0.9.0 e anteriores

Ver histórico de commits no repositório.
