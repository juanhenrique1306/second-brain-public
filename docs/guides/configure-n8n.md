# Configurar n8n

## Objetivo

Conectar:

```text
Telegram
   ↓
n8n
   ↓
Brain API
   ↓
Telegram
```

## Credenciais necessárias

### Telegram

Crie uma credencial `Telegram API`.

### Brain API

Crie uma credencial `Header Auth`:

```text
X-API-Key: <BRAIN_API_KEY>
```

## Workflow mínimo

```text
Telegram Trigger
      ↓
HTTP Request
      ↓
Send a text message
```

## HTTP Request

```text
Method: POST
URL: http://second-brain-api:8000/ask
Authentication: Header Auth
Body Content Type: JSON
```

Body:

```json
{
  "query": "{{ $json.message.text }}"
}
```

## Resposta

O node de Telegram deve usar o campo `answer` retornado pela API.

```text
{{ $node["HTTP Request"].json["answer"] }}
```

## Importar workflow de exemplo

Use:

```text
examples/n8n/second-brain-telegram-workflow.json
```

Depois da importação:

1. associe a credencial do Telegram;
2. associe a credencial de Header Auth;
3. teste o Trigger;
4. teste o HTTP Request;
5. teste a resposta;
6. publique o workflow.

## Segurança

Não exporte nem publique credenciais reais.

O arquivo de exemplo deve conter apenas nomes genéricos de credenciais.
