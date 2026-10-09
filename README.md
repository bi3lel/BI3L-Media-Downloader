<p align="center">
  <img src="assets/app_icon.png" width="128" alt="BI3L Media Downloader">
</p>

<h1 align="center">BI3L Media Downloader</h1>

<p align="center">
  Downloader de mídia simples para Windows, com interface escura em Português (Brasil) e English.
</p>

<p align="center">
  <a href="../../releases/latest"><strong>Baixar a versão mais recente</strong></a>
</p>

> Use apenas com conteúdo próprio, em domínio público ou que você tenha autorização para salvar. Respeite os termos das plataformas e as leis aplicáveis.

## Nova interface 2.6.0

O logo e o nome originais BI3L foram preservados. A engrenagem fica no canto inferior esquerdo; a pasta de destino aparece apenas nas Configurações, com controles centralizados. Minimizar, maximizar/restaurar e fechar ficam no canto superior direito. A nova interface mantém filas, Drive, playlists, Spotify e conversão MP4.

## Recursos

- YouTube, Instagram, TikTok, Twitch Clips, X e links públicos do Spotify
- Vídeo MP4 com ou sem áudio
- Áudio MP3 em 320, 256, 192 ou 128 kbps
- Qualidades de vídeo de 360p até 2160p, além de Melhor disponível
- Vários links em uma fila
- Seleção de itens em playlists, álbuns e coleções compatíveis
- Carregamento progressivo de playlists grandes
- Progresso individual com nome, porcentagem, velocidade, tamanho e tempo restante
- Interface completa em English e Português (Brasil)
- Atualização do mecanismo yt-dlp pelas Configurações
- Pasta de downloads configurável

## Novidades da versão 2.5.0

- **Google Drive público:** cole um link de arquivo ou pasta. A pasta é listada sem baixar os arquivos; marque os desejados e clique em Continuar e Baixar. Subpastas são preservadas, arquivos são salvos no formato original em `Google Drive` e arquivos existentes não são sobrescritos. Documentos Google usam o formato de exportação do gdown. Não inclui login privado nem ignora limites do Google.
- **Outros sites:** a tela inicial mantém o logo BI3L, o título e os controles de URL; os ícones dos serviços e suas explicações ficam fora da tela inicial. As explicações ficam neste README. URLs diretas, páginas e streams HLS/DASH compatíveis usam os extratores do yt-dlp. URLs sem resolução informada também são aceitas. Não há garantia para todos os sites, DRM ou conteúdo que exige login.
- **Conversão mais rápida:** teste real de NVIDIA NVENC, Intel Quick Sync e AMD AMF, com fallback para CPU se necessário. CPU usa preset `veryfast`; velocidade e tamanho dependem do hardware e do vídeo. Mantém H.264 de 8 bits, taxa de quadros constante e AAC.
- **Spotify:** metadados pelo ID correto, comparação de artista, título, duração e versão, além do álbum quando disponível. Resultados incertos abrem uma seleção antes de baixar; é possível pular a música. Vale também para playlists e álbuns. O ID identifica a faixa no Spotify, não um stream de áudio público.

## MP4 para VEGAS e outros editores

O aplicativo converte todos os downloads MP4 para vídeo H.264 High, 8 bits, 4:2:0 e taxa de quadros constante, com áudio AAC-LC estéreo a 48 kHz. A opção sem áudio usa a mesma conversão de vídeo. Também funciona com links diretos e playlists.

Antes, um arquivo `.mp4` podia conter AV1, VP9 ou Opus, incompatíveis com alguns editores. A conversão agora ocorre mesmo quando o arquivo já é MP4. Ela demora mais, precisa de espaço para uma segunda cópia e pode aumentar o tamanho do arquivo. A codificação usa CRF 18 na CPU ou ajustes de qualidade específicos na GPU; há perda de qualidade. Aguarde a etapa de conversão terminar; em caso de falha, o download original é preservado e um erro é exibido.

Arquivos antigos não são alterados automaticamente: baixe novamente com esta versão ou faça uma cópia de segurança e execute `python video_compat.py "caminho/para/video.mp4"` na instalação pelo código-fonte. Use `--silent` para remover o áudio. Editores antigos ainda podem limitar resolução e taxa de quadros. Não inclui mapeamento de tons HDR para SDR.

## Instalação

Abra a página de [Releases](../../releases/latest) e escolha uma opção:

- **`BI3L.Media.Downloader.zip`:** pacote portátil pequeno; extraia a pasta e abra `BI3L Media Downloader.exe`. Requer Python 3.11 ou mais recente, WebView2 e internet na primeira execução para preparar as dependências.
- **`BI3L.Media.Downloader.Setup.exe`:** instalador offline completo, sem precisar de Python ou internet durante a instalação. Os downloads de mídia ainda precisam de conexão.

O Windows pode exibir “Editor desconhecido” enquanto o executável não possuir assinatura digital. Confira o hash SHA-256 publicado na mesma Release.

## Como usar

1. Cole um link, ou vários links separados por espaço ou por uma linha nova.
2. Selecione os itens quando o link contiver uma playlist ou coleção.
3. Escolha MP4 ou MP3 e a qualidade.
4. Clique em **Download**.

O destino padrão é `%USERPROFILE%\Downloads\BI3L Media Downloader`. Ele pode ser alterado no ícone de engrenagem.

## Observação sobre Spotify

O aplicativo não baixa nem descriptografa o áudio protegido do Spotify. Ele lê metadados públicos do link e procura uma fonte pública correspondente, compatível com o yt-dlp. Playlists privadas e conteúdo protegido não são acessados.

## Executar pelo código-fonte

Requisitos: Windows 10/11, Python 3.11+, WebView2 e Node.js 22.12+ para compilar a interface a partir do código-fonte.

```bat
setup.bat
run.bat
```

Veja [BUILDING.md](BUILDING.md) para gerar o launcher e o instalador offline.

## Privacidade e responsabilidade

- O aplicativo não possui telemetria nem conta própria.
- As preferências ficam armazenadas localmente.
- O fallback do TikTok pode enviar somente a URL pública da publicação para `tikwm.com` quando o extrator local conhecido falhar.

Leia [PRIVACY.md](PRIVACY.md), [DISCLAIMER.md](DISCLAIMER.md) e [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) antes de redistribuir o programa.

## Licença

O código-fonte é disponibilizado sob a [GNU GPL v3.0](LICENSE). O mascote original do BI3L Media Downloader não é licenciado separadamente para uso como marca de outro produto. Nomes e logotipos das plataformas pertencem aos seus respectivos titulares e são mostrados apenas para identificação.

Copyright © 2026 BI3L.
