# Troubleshooting

## Brain API retorna 401

Verifique:

```text
X-API-Key
```

e confirme que o valor é igual a:

```env
BRAIN_API_KEY
```

## Brain API retorna 503

Pode indicar que `BRAIN_API_KEY` não foi configurada.

## Qdrant indisponível

Verifique:

```bash
docker ps
docker logs second-brain-qdrant
curl http://127.0.0.1:6333/collections
```

## Indexador não encontra Vault

Confirme:

```env
VAULT_PATH=/vault
```

e o volume no Compose.

## n8n não alcança a Brain API

Dentro da rede Docker, use:

```text
http://second-brain-api:8000
```

Não use `127.0.0.1` para outro container.

## Telegram `chat not found`

Confirme que o Chat ID vem do Trigger correto e que a credencial está associada ao mesmo bot.

## Telegram `can't parse entities`

Remova Parse Mode e teste texto simples.

Depois implemente escape adequado para HTML ou MarkdownV2.

## 403 no editor n8n pela VPN

Confirme qual IP o Traefik realmente enxerga.

Use:

```bash
sudo tcpdump -ni any 'tcp dst port 443'
```

ou habilite access logs do Traefik.

Em cenários de NAT, o IP visto pelo Traefik pode ser diferente do IP do cliente VPN.

## HTTP Request do n8n demora muito

Teste diretamente a Brain API e separe tempos de:

- busca;
- Qdrant;
- embeddings;
- Gemini.

Se o gargalo for o modelo externo, configure timeout e tratamento de erro.

## Modelo de embeddings demora ao iniciar

A primeira execução pode baixar o modelo.

Confirme:

```text
HF_HOME=/models/huggingface
```

e use volume persistente para evitar downloads repetidos.
