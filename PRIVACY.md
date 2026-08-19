# Privacidade

## Dados armazenados localmente

BI3L Media Downloader não cria conta e não possui telemetria própria. As preferências, incluindo idioma e pasta de destino, são salvas em:

`%APPDATA%\BI3L Media Downloader\settings.json`

Os arquivos baixados vão para a pasta escolhida pelo usuário. Arquivos temporários de conversão e mesclagem usam a pasta temporária do Windows e são removidos ao concluir ou cancelar quando possível.

## Conexões externas

Para analisar e baixar mídia, o aplicativo e o yt-dlp conectam-se ao endereço informado e aos servidores necessários para obter o conteúdo público.

- **TikTok:** o aplicativo tenta o yt-dlp local primeiro. Somente quando o extrator retorna a falha conhecida de página/desafio, a URL pública da publicação pode ser enviada a `tikwm.com` para obter um link temporário de mídia.
- **Spotify:** o aplicativo consulta metadados públicos do Spotify e procura uma fonte pública correspondente. Ele não acessa, baixa nem descriptografa os streams protegidos do Spotify.
- **Atualizações:** a opção de atualizar o downloader consulta e baixa uma versão atual do yt-dlp.

O projeto não controla as práticas de privacidade desses serviços externos. Consulte as políticas de cada serviço antes de usá-lo.
