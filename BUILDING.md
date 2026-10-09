# Compilação no Windows

## Executar pelo código-fonte

Requisitos:

- Windows 10 ou 11
- Python 3.11 ou mais recente no PATH
- Node.js 22.12+ para compilar webui
- Microsoft WebView2 Runtime
- Conexão com a internet durante a preparação

Execute:

```bat
setup.bat
run.bat
```

O `setup.bat` cria `.venv`, instala os pacotes de `requirements.txt` e prepara yt-dlp e FFmpeg. Esses arquivos gerados não devem ser adicionados ao Git.

## Launcher pequeno

O código do launcher nativo está em `build/`. Ele abre o aplicativo e executa a preparação inicial quando necessário. Para recompilá-lo, use um compilador C para Windows e incorpore:

- `build/launcher.rc`
- `build/launcher.manifest`
- `assets/app_icon.ico`

O executável compilado deve ficar ao lado da pasta `App` no pacote portátil.

## Instalador offline

1. Instale o [Inno Setup 6](https://jrsoftware.org/isdl.php).
2. Execute `cd webui`, `npm ci`, `npm run build` e `npx tsc --noEmit`. Copie o conteúdo do projeto, incluindo `webui/dist`, para a pasta `App` do Offline Builder.
3. Abra `offline_builder/Build Offline Installer.bat`.
4. O arquivo final será criado em `Output\BI3L Media Downloader Setup.exe`.

O builder baixa as ferramentas atuais uma vez e cria um instalador autossuficiente. O resultado não é assinado digitalmente; uma assinatura Authenticode de um certificado confiável é necessária para identificar o editor no Windows.

Antes de publicar uma versão, execute:

```bat
python -m unittest discover -p "test_*.py"
python -m py_compile app.py core.py i18n.py strip_audio.py video_compat.py drive_support.py spotify_match.py desktop_web.py
```
