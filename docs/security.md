# Segurança

Este documento complementa o `SECURITY.md` da raiz e descreve a arquitetura de segurança recomendada para o Second Brain.

## Princípios

- não expor serviços internos sem necessidade;
- usar HTTPS;
- manter segredos fora do Git;
- limitar interfaces administrativas;
- separar redes internas de redes de borda;
- usar autenticação na Brain API;
- tratar o Vault como dado potencialmente sensível.

## Serviços que não devem ser públicos

Idealmente:

```text
PostgreSQL
Qdrant
Brain API
```

devem permanecer internos ou restritos.

## Brain API

Rotas protegidas utilizam:

```text
X-API-Key
```

A chave deve vir de:

```env
BRAIN_API_KEY
```

Nunca deixe a chave hardcoded no código.

## n8n

Recomendações:

- use `N8N_ENCRYPTION_KEY`;
- mantenha essa chave estável;
- não publique o valor;
- proteja o editor com VPN ou allowlist;
- exponha publicamente apenas webhooks necessários;
- mantenha as credenciais dentro do mecanismo de credenciais do n8n.

## Traefik

A interface privada do n8n pode ser protegida por allowlist.

Exemplo:

```text
192.168.1.0/24
10.8.0.0/24
```

Em ambientes com Docker NAT ou hairpin NAT, o Traefik pode enxergar o gateway Docker em vez do IP original do cliente VPN. Nessa situação, confirme o IP visto pelo Traefik antes de ajustar a allowlist.

Não libere redes Docker inteiras sem necessidade.

## Qdrant

Se precisar de debug local, prefira bind em loopback:

```text
127.0.0.1:6333
127.0.0.1:6334
```

Evite:

```text
0.0.0.0:6333
```

em servidores acessíveis por outras redes.

## PostgreSQL

Não exponha a porta do banco publicamente.

O n8n deve acessar PostgreSQL pela rede Docker.

## Vault

Não publique seu Vault real.

O Vault pode conter:

- dados pessoais;
- informações de trabalho;
- credenciais acidentalmente anotadas;
- decisões;
- histórico;
- documentos privados.

Use apenas conteúdo fictício no diretório `examples/sample-vault`.

## Gemini e privacidade

Mesmo que o Vault esteja local, trechos usados como contexto podem ser enviados para uma API externa de IA.

Antes de usar o sistema com informações sensíveis, avalie:

- o tipo de conteúdo;
- o provedor utilizado;
- termos e políticas aplicáveis;
- necessidade de filtragem ou classificação prévia.

## Git

Antes de cada push:

```bash
git status
```

Procure segredos:

```bash
grep -RniE \
'token|password|secret|api[_-]?key|authorization' \
. \
--exclude-dir=.git \
--exclude-dir=.venv
```

Considere usar ferramentas especializadas como `gitleaks` em CI.

## Credencial exposta

Se uma credencial for publicada:

1. considere-a comprometida;
2. revogue ou regenere;
3. atualize os serviços dependentes;
4. remova do conteúdo atual;
5. verifique o histórico Git;
6. reescreva o histórico se necessário.

## Docker

Evite:

```text
privileged: true
```

e montagens do Docker socket sem necessidade.

Use:

- redes separadas;
- volumes explícitos;
- portas mínimas;
- imagens atualizadas.
