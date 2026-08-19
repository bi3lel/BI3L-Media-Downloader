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

## Instalação

Abra a página de [Releases](../../releases/latest) e escolha uma opção:

- **`BI3L.Media.Downloader.zip`:** pacote portátil pequeno; extraia a pasta e abra `BI3L Media Downloader.exe`. Requer Python 3.11 ou mais recente e internet na primeira execução para preparar as dependências.
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

Requisitos: Windows 10/11 e Python 3.11+.

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
