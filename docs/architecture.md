# Arquitetura

Este documento descreve a arquitetura do **Second Brain** e o papel de cada componente.

## Visão geral

```text
Obsidian
   ↓
Syncthing
   ↓
Vault Markdown
   ↓
Brain Indexer
   ↓
Qdrant
   ↓
Brain API
   ↓
Gemini
   ↓
n8n
   ↓
Telegram
```

O sistema separa armazenamento, indexação, busca semântica, geração de resposta e automação.

## Componentes

### Obsidian

Responsável pela criação e organização das notas.

As notas permanecem como arquivos Markdown comuns, o que evita dependência do restante da aplicação para leitura ou edição do conteúdo.

### Syncthing

Pode ser usado para sincronizar o Vault entre o computador do usuário e o servidor.

Exemplo:

```text
Notebook
   ↓
Syncthing
   ↓
Servidor
```

O Syncthing não é obrigatório para o funcionamento lógico do projeto. O requisito é que o Vault esteja disponível para os containers.

### Vault

O Vault é o conjunto de arquivos Markdown usado como fonte de conhecimento.

Dentro dos containers ele é montado em:

```text
/vault
```

### Brain Indexer

Responsável por:

1. detectar notas novas ou modificadas;
2. ler Markdown e frontmatter;
3. dividir o conteúdo em seções e chunks;
4. gerar embeddings;
5. armazenar vetores e metadados no Qdrant.

O serviço principal é:

```text
watch_indexer.py
```

Também existe:

```text
index_vault.py
```

para indexação manual ou reconstrução controlada do índice.

### Modelo de embeddings

O modelo padrão é:

```text
intfloat/multilingual-e5-base
```

Consultas e documentos são convertidos em vetores para permitir busca por significado.

### Qdrant

Banco vetorial responsável por armazenar:

- embeddings;
- texto original;
- título;
- origem;
- pasta;
- seção;
- metadados;
- tipo do documento.

O Qdrant não deve ser exposto publicamente.

### Brain API

API em FastAPI responsável por:

- autenticação via `X-API-Key`;
- busca semântica;
- roteamento de intenção;
- consulta ao Qdrant;
- leitura e escrita controlada no Vault;
- análise de memórias;
- integração com Gemini;
- geração de resposta.

Principais endpoints:

```text
GET  /
GET  /health

POST /search
POST /route
POST /memory/analyze
POST /memory/write
POST /ask
```

### Gemini

Modelo de linguagem usado para gerar respostas a partir da pergunta e do contexto recuperado.

Quando o sistema usa informações do Vault, trechos relevantes podem ser enviados para a API externa do modelo. Avalie cuidadosamente quais dados podem sair da sua infraestrutura.

### n8n

Responsável pela automação e integração entre serviços.

Fluxo básico:

```text
Telegram Trigger
      ↓
HTTP Request
      ↓
Brain API /ask
      ↓
Send Message
```

### PostgreSQL

Usado pelo n8n para persistir configurações e dados internos.

### Telegram

Interface conversacional opcional para consultar o sistema.

### Traefik

Reverse proxy usado para:

- HTTPS;
- roteamento;
- exposição de webhooks;
- proteção da interface do n8n;
- allowlist de LAN/VPN.

## Redes Docker

A arquitetura usa duas redes principais:

```text
second-brain-net
proxy
```

### `second-brain-net`

Rede interna entre:

- PostgreSQL;
- Qdrant;
- Brain API;
- Brain Indexer;
- n8n.

### `proxy`

Rede externa compartilhada com um Traefik já existente.

## Fluxo de uma consulta

```text
Usuário
   ↓
Telegram
   ↓
n8n
   ↓
Brain API
   ↓
classificação de intenção
   ↓
Qdrant
   ↓
contexto relevante
   ↓
Gemini
   ↓
Brain API
   ↓
n8n
   ↓
Telegram
```

## Fluxo de indexação

```text
Arquivo Markdown
      ↓
watch_indexer.py
      ↓
leitura do conteúdo
      ↓
chunking
      ↓
embedding
      ↓
Qdrant
```

## Diagrama

A imagem de arquitetura pode ser adicionada em:

```text
docs/images/architecture.png
```

e referenciada no README principal com:

```markdown
![Arquitetura do Second Brain](docs/images/architecture.png)
```
