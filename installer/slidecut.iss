; Instalador do slidecut.
;
; Instala o programa, cria os atalhos e resolve a dependencia de conversao.
;
; Converter apresentacoes e documentos em PDF usa o LibreOffice quando ele
; existe: mesma versao em qualquer maquina, previsivel. O Microsoft Office
; entra como reserva, para quem nao tem LibreOffice ou quando este falhar
; num arquivo especifico.
;
; Mesmo assim o LibreOffice e oferecido a todo mundo que ainda nao o tem: ter
; os dois instalados e o que garante que qualquer material do time seja
; cortavel, mesmo os poucos casos em que um dos dois recusa um arquivo.
;
; Ele nao pode ser embutido aqui (instalador proprio, ~350 MB, licenca MPL),
; entao o setup baixa o instalador oficial e confere o SHA-256 publicado pela
; The Document Foundation antes de executar.
;
; Compilar: ISCC.exe installer\slidecut.iss

#define AppName        "slidecut"
#define AppVersion     "0.10.8"
#define AppPublisher   "Alex Moreira Productions"
#define AppExe         "slidecut.exe"

; Usa a pasta "stable" (versao atual), nao "old" (arquivo historico): so a
; "stable" passa pelo redirecionador de mirrors da The Document Foundation.
; O arquivo historico serve direto de um unico servidor de origem sem rede de
; espelhos — medido em ~140 KB/s contra ~20 MB/s pelo mirror, 140x mais lento.
; Contrapartida: este link muda a cada lancamento novo do LibreOffice, entao
; versao e hash abaixo precisam ser atualizados quando isso acontecer.
#define LoVersion      "26.2.5"
#define LoFile         "LibreOffice_26.2.5_Win_x86-64.msi"
#define LoUrl          "https://download.documentfoundation.org/libreoffice/stable/26.2.5/win/x86_64/LibreOffice_26.2.5_Win_x86-64.msi"
#define LoSha256       "f15ba07bfcb0186986cf3171063506f5d207c11f8cc051ba0d135209e9e915f9"

[Setup]
AppId={{8F3C1D24-6B2E-4E77-9C3A-1D5B7E9A4C10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=..\dist
OutputBaseFilename=slidecut-setup-{#AppVersion}
SetupIconFile=..\src\slidecut\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na Area de Trabalho"; GroupDescription: "Atalhos:"
Name: "libreoffice"; \
  Description: "Baixar e instalar o LibreOffice (recomendado, ~350 MB)"; \
  GroupDescription: "Compatibilidade de conversao:"; \
  Check: LibreOfficeMissing

[Files]
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md";      DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#AppName}";        Filename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir o {#AppName} agora"; Flags: nowait postinstall skipifsilent

[Code]
var
  DownloadPage: TDownloadWizardPage;
  NeedsLibreOffice: Boolean;

function LibreOfficeInstalled(): Boolean;
{ Procura o soffice.exe nos caminhos de instalacao padrao das duas
  arquiteturas. E o mesmo criterio que o programa usa em tempo de execucao. }
begin
  Result :=
    FileExists(ExpandConstant('{commonpf64}\LibreOffice\program\soffice.exe')) or
    FileExists(ExpandConstant('{commonpf32}\LibreOffice\program\soffice.exe'));
end;

function MicrosoftOfficeInstalled(): Boolean;
{ O programa prefere o LibreOffice quando ele existe. O Office entra como
  reserva: cobre os poucos arquivos que o LibreOffice se recusa a exportar. }
begin
  Result :=
    RegKeyExists(HKEY_CLASSES_ROOT, 'PowerPoint.Application') or
    RegKeyExists(HKEY_CLASSES_ROOT, 'Word.Application') or
    RegKeyExists(HKEY_CLASSES_ROOT, 'Excel.Application');
end;

function LibreOfficeMissing(): Boolean;
{ A opcao de instalar o LibreOffice so aparece para quem ainda nao o tem —
  inclusive para quem ja tem o Office, porque os dois se completam. }
begin
  Result := not LibreOfficeInstalled();
end;

function OnDownloadProgress(const Url, Filename: String; const Progress, ProgressMax: Int64): Boolean;
begin
  if ProgressMax > 0 then
    DownloadPage.SetProgress(Progress, ProgressMax);
  Result := True;
end;

procedure InitializeWizard();
begin
  DownloadPage := CreateDownloadPage(
    'Baixando o LibreOffice',
    'Alguns arquivos so convertem pelo LibreOffice, mesmo em computadores com Office.',
    @OnDownloadProgress);
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = DownloadPage.ID) and (not NeedsLibreOffice);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;

  { A caixa marcada na pagina de tarefas ja e o consentimento; nao ha por que
    perguntar de novo. }
  if CurPageID = wpReady then
    NeedsLibreOffice := WizardIsTaskSelected('libreoffice');

  if (CurPageID = wpReady) and NeedsLibreOffice then
  begin
    DownloadPage.Clear;
    { O hash e o publicado pela The Document Foundation: sem ele, um mirror
      comprometido poderia entregar outro executavel. }
    DownloadPage.Add('{#LoUrl}', '{#LoFile}', '{#LoSha256}');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;

        DownloadPage.SetText('Instalando o LibreOffice...', 'Isso pode levar alguns minutos.');
        if not Exec('msiexec.exe',
                    '/i "' + ExpandConstant('{tmp}\{#LoFile}') + '" /qn /norestart',
                    '', SW_SHOW, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
          MsgBox(
            'Nao foi possivel instalar o LibreOffice automaticamente.' + #13#10#13#10 +
            'O {#AppName} sera instalado assim mesmo. Se voce tem Office, a maioria ' +
            'dos arquivos continua convertendo; para os que o Office recusar, ' +
            'instale o LibreOffice depois, em libreoffice.org.',
            mbInformation, MB_OK);
      except
        MsgBox(
          'O download do LibreOffice falhou: ' + GetExceptionMessage + #13#10#13#10 +
          'O {#AppName} sera instalado assim mesmo. Voce pode instalar o ' +
          'LibreOffice depois, em libreoffice.org.',
          mbInformation, MB_OK);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;
