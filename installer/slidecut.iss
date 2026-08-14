; Instalador do slidecut.
;
; Instala o programa, cria os atalhos e resolve a dependencia de conversao.
;
; Converter apresentacoes e documentos em PDF exige Microsoft Office ou
; LibreOffice. Quem tem Office nao precisa de mais nada — o programa usa o
; proprio aplicativo que criou o arquivo. So quando a maquina nao tem nenhum
; dos dois o setup oferece baixar o LibreOffice: ele nao pode ser embutido
; aqui (instalador proprio, ~350 MB, licenca MPL). O download e conferido pelo
; SHA-256 publicado pela The Document Foundation antes de ser executado.
;
; Compilar: ISCC.exe installer\slidecut.iss

#define AppName        "slidecut"
#define AppVersion     "0.3.0"
#define AppPublisher   "slidecut"
#define AppExe         "slidecut.exe"

#define LoVersion      "25.8.7.2"
#define LoFile         "LibreOffice_25.8.7.2_Win_x86-64.msi"
#define LoUrl          "https://downloadarchive.documentfoundation.org/libreoffice/old/25.8.7.2/win/x86_64/LibreOffice_25.8.7.2_Win_x86-64.msi"
#define LoSha256       "4773ad68edc890c7d02ae0733710af118e7e95398a4d05077429182941604ec6"

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
{ O programa prefere o Office quando ele existe: converte pelo proprio
  aplicativo que criou o arquivo, com fidelidade exata e sem instalar nada.
  Quem tem Office nao precisa baixar os 350 MB do LibreOffice. }
begin
  Result :=
    RegKeyExists(HKEY_CLASSES_ROOT, 'PowerPoint.Application') or
    RegKeyExists(HKEY_CLASSES_ROOT, 'Word.Application') or
    RegKeyExists(HKEY_CLASSES_ROOT, 'Excel.Application');
end;

function ConverterAvailable(): Boolean;
begin
  Result := MicrosoftOfficeInstalled() or LibreOfficeInstalled();
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
    'O {#AppName} usa o LibreOffice para converter apresentacoes e documentos em PDF.',
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

  if CurPageID = wpReady then
  begin
    NeedsLibreOffice := not ConverterAvailable();
    if NeedsLibreOffice then
    begin
      if MsgBox(
        'Este computador nao tem Microsoft Office nem LibreOffice.' + #13#10#13#10 +
        'Um dos dois e necessario apenas para converter apresentacoes e documentos ' +
        '(.pptx, .docx e afins) em PDF. Arquivos que ja sao PDF funcionam sem eles.' + #13#10#13#10 +
        'Baixar e instalar o LibreOffice ' + '{#LoVersion}' + ' agora? ' +
        'Sao cerca de 350 MB.',
        mbConfirmation, MB_YESNO) = IDNO then
      begin
        NeedsLibreOffice := False;
        Exit;
      end;
    end;
  end;

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
            'O {#AppName} sera instalado assim mesmo e ja funciona com arquivos PDF. ' +
            'Para converter apresentacoes, instale o Microsoft Office ou o ' +
            'LibreOffice (libreoffice.org).',
            mbInformation, MB_OK);
      except
        MsgBox(
          'O download do LibreOffice falhou: ' + GetExceptionMessage + #13#10#13#10 +
          'O {#AppName} sera instalado assim mesmo e ja funciona com arquivos PDF.',
          mbInformation, MB_OK);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;
