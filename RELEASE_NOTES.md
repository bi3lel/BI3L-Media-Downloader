# BI3L Media Downloader v2.4.1

## Correção de compatibilidade MP4 / VEGAS

- Conversão automática para H.264 High de 8 bits (4:2:0), taxa de quadros constante e áudio AAC-LC estéreo a 48 kHz.
- Corrige downloads MP4 que continham VP9, AV1, Opus ou vídeo de 10 bits e não abriam em alguns editores.
- Inclui MP4 sem áudio, playlists e links diretos; MP3 permanece inalterado.
- Preserva o download original se a conversão falhar e mostra o erro.
- A conversão requer tempo e espaço adicionais. Baixe novamente os vídeos antigos para aplicar a correção.

## MP4 / VEGAS compatibility fix

All MP4 downloads now convert to 8-bit H.264 video with constant frame rate and AAC stereo audio. This fixes the previous container-only merge that could leave unsupported codecs inside an MP4. Silent videos, direct links and playlists are covered. Conversion takes extra time and disk space; old downloads must be downloaded again or converted with the source helper. The original is preserved if conversion fails.

## Destaques

- Interface em English e Português (Brasil)
- Carregamento progressivo de playlists grandes
- Fila de vários links e seleção de itens
- Progresso detalhado reiniciado para cada mídia
- MP4 com áudio, MP4 sem áudio e MP3
- Suporte a Twitch Clips e coleções públicas compatíveis
- Atualização do yt-dlp dentro das Configurações
- Seleção automática do mecanismo yt-dlp mais recente disponível
- Downloads fragmentados, retentativas e limpeza segura ao cancelar
- Identidade visual BI3L Media Downloader

## Downloads

- `BI3L.Media.Downloader.zip`: pacote portátil pequeno com launcher do Windows.
- `BI3L.Media.Downloader.Setup.exe`: instalador offline completo.
- `SHA256SUMS.txt`: hashes para verificar os arquivos publicados.

Leia o README, os avisos de privacidade e os componentes de terceiros antes de redistribuir.
