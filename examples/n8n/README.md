# Exemplo de workflow n8n

Este diretório contém um workflow de exemplo para integrar Telegram e Brain API.

Arquivo:

```text
second-brain-telegram-workflow.json
```

## Fluxo

```text
Telegram Trigger
      ↓
HTTP Request
      ↓
Brain API /ask
      ↓
Send Message
```

## Após importar

Crie/associe duas credenciais:

### Telegram Credential

Tipo:

```text
Telegram API
```

Use o token do seu próprio bot.

### Brain API Header Auth

Tipo:

```text
Header Auth
```

Configure:

```text
X-API-Key: <BRAIN_API_KEY>
```

## Observação

O arquivo de exemplo não contém tokens nem chaves reais.

Depois de importar, associe as credenciais manualmente e teste o workflow antes de ativá-lo.
