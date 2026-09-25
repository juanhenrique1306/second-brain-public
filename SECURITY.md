# Security Policy

Este projeto lida com informações pessoais, automação, APIs externas e serviços de rede.

## Nunca publique

- arquivos `.env`;
- tokens de Telegram;
- chaves do Gemini;
- chaves do Cloudflare;
- credenciais do PostgreSQL;
- `N8N_ENCRYPTION_KEY`;
- chaves SSH;
- certificados privados;
- dumps de banco;
- conteúdo real do Obsidian Vault;
- backups;
- logs com dados sensíveis.

## Credencial exposta

Se uma credencial for exposta:

1. considere-a comprometida;
2. revogue ou regenere imediatamente;
3. atualize os serviços dependentes;
4. remova-a dos arquivos;
5. verifique o histórico Git;
6. reescreva o histórico se necessário.

## Recomendações

- mantenha Qdrant e PostgreSQL sem exposição pública;
- mantenha a Brain API em rede interna quando possível;
- use autenticação por API key;
- exponha apenas os webhooks necessários;
- proteja interfaces administrativas com VPN ou allowlist;
- utilize HTTPS;
- não exponha dashboards administrativos sem autenticação;
- evite containers privilegiados;
- use redes Docker separadas;
- não exponha portas internas sem necessidade.

## Relato de vulnerabilidades

Não publique detalhes sensíveis em issue aberta. Inclua componente afetado, impacto, passos mínimos para reprodução e versão ou commit afetado, sem expor credenciais ou dados reais.
