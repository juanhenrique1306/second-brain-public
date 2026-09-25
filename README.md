# Second Brain

Um sistema pessoal de memória aumentada que conecta Obsidian, busca vetorial, automação e inteligência artificial.

O projeto transforma anotações Markdown em uma base de conhecimento consultável por linguagem natural.

## Como funciona

```text
Obsidian
   ↓
Syncthing
   ↓
Brain Indexer
   ↓
Qdrant
   ↓
Brain API (FastAPI)
   ↓
Gemini
   ↓
n8n
   ↓
Telegram
```

## Componentes

- Obsidian
- Syncthing
- FastAPI
- Qdrant
- Sentence Transformers
- Gemini
- n8n
- Telegram Bot
- PostgreSQL
- Docker
- Traefik

## Estrutura

```text
second-brain/
├── brain-api/
├── brain-indexer/
├── compose/
├── docs/
│   ├── guides/
│   └── images/
├── examples/
│   ├── n8n/
│   └── sample-vault/
├── scripts/
├── tests/
├── .env.example
├── .gitignore
├── CONTRIBUTING.md
├── LICENSE
├── README.md
└── SECURITY.md
```

## Segurança

Não publique tokens, chaves de API, senhas, dados pessoais, conteúdo real do Vault, bancos, backups ou arquivos `.env`.

## Configuração

```bash
cp .env.example .env
```

Edite o `.env` com suas próprias credenciais e nunca o versione.

## Status

Projeto em desenvolvimento.

## Licença

MIT.
