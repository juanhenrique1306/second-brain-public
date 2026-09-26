# Configurar Telegram

## 1. Criar o bot

Crie um bot usando o BotFather no Telegram e guarde o token em local seguro.

Não coloque o token no GitHub.

## 2. Criar a credencial no n8n

No n8n:

```text
Credentials
→ New Credential
→ Telegram API
```

Cole o token do bot.

Sugestão de nome:

```text
Telegram Credential
```

## 3. Adicionar Telegram Trigger

Configure:

```text
Updates: message
```

## 4. Enviar a mensagem para a Brain API

Use um node `HTTP Request`:

```text
Method: POST
URL: http://second-brain-api:8000/ask
```

Body:

```json
{
  "query": "{{ $json.message.text }}"
}
```

A sintaxe de expressão pode variar conforme o modo do campo no n8n. Se o campo já estiver em modo Expression, evite introduzir um `=` literal no valor final.

## 5. Configurar autenticação

Use uma credencial de Header Auth:

```text
Header: X-API-Key
Value: mesmo valor de BRAIN_API_KEY
```

## 6. Responder pelo Telegram

Use o node `Send Message`.

Chat ID:

```text
{{ $node["Telegram Trigger"].json["message"]["chat"]["id"] }}
```

Texto:

```text
{{ $node["HTTP Request"].json["answer"] }}
```

## 7. Parse Mode

Se respostas de IA gerarem erro como:

```text
can't parse entities
```

comece enviando texto simples, sem Parse Mode.

Depois, se desejar formatação, implemente escape/conversão adequada para HTML ou MarkdownV2.

## 8. Publicar workflow

Após testar, publique/ative o workflow.

Lembre-se: um bot do Telegram utiliza um webhook por vez.
