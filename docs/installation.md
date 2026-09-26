# Instalação

Este guia mostra uma instalação base do Second Brain usando Docker Compose.

## Pré-requisitos

- Linux ou outro sistema com Docker;
- Docker Compose;
- Git;
- chave da API Gemini;
- diretório para o Vault;
- Traefik opcionalmente já instalado;
- bot do Telegram, caso use o fluxo via Telegram.

## 1. Clonar o repositório

```bash
git clone https://github.com/juanhenrique1306/second-brain-public.git
cd second-brain-public
```

## 2. Criar o arquivo `.env`

```bash
cp .env.example .env
```

Edite:

```bash
nano .env
```

No mínimo, configure:

```env
BRAIN_API_KEY=gere_uma_chave_forte
GEMINI_API_KEY=sua_chave_gemini

POSTGRES_PASSWORD=gere_uma_senha_forte
N8N_ENCRYPTION_KEY=gere_uma_chave_forte
```

## 3. Configurar o Vault

O container espera o Vault em:

```text
/vault
```

O caminho do host deve ser definido separadamente no Compose por uma variável de storage, por exemplo:

```env
VAULT_DATA_PATH=./data/vault
```

Evite usar a mesma variável para representar simultaneamente o caminho do host e o caminho interno do container.

## 4. Criar diretórios de dados

Exemplo:

```bash
mkdir -p \
  data/vault \
  data/qdrant \
  data/postgres \
  data/n8n \
  data/models/huggingface
```

## 5. Rede do Traefik

O Compose de exemplo assume que a rede externa `proxy` já existe.

Verifique:

```bash
docker network ls
```

Se necessário:

```bash
docker network create proxy
```

Se você não pretende usar Traefik, adapte o Compose antes de subir o ambiente.

## 6. Validar o Compose

```bash
docker compose \
  --env-file .env \
  -f compose/docker-compose.example.yml \
  config
```

## 7. Construir as imagens

```bash
docker compose \
  --env-file .env \
  -f compose/docker-compose.example.yml \
  build
```

## 8. Subir os serviços

```bash
docker compose \
  --env-file .env \
  -f compose/docker-compose.example.yml \
  up -d
```

## 9. Verificar containers

```bash
docker ps
```

Esperado:

```text
second-brain-postgres
second-brain-qdrant
second-brain-api
second-brain-indexer
second-brain-n8n
```

## 10. Testar a Brain API

```bash
curl http://127.0.0.1:8000/health
```

## 11. Testar uma consulta

```bash
curl \
  -X POST \
  http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: SUA_BRAIN_API_KEY" \
  -d '{"query":"O que é o Second Brain?"}'
```

## 12. Verificar logs

```bash
docker logs second-brain-api
docker logs second-brain-indexer
docker logs second-brain-qdrant
docker logs second-brain-n8n
```

## Observação sobre o modelo

Na primeira inicialização, o modelo de embeddings pode ser baixado e carregado, o que pode levar algum tempo.

## Próximos passos

- importar o workflow n8n;
- configurar credencial do Telegram;
- configurar Header Auth para a Brain API;
- configurar Traefik;
- sincronizar o Vault com Syncthing;
- testar uma nota fictícia.
