# Indexar o Vault

## Monitoramento contínuo

O container `second-brain-indexer` executa:

```text
watch_indexer.py
```

Ele monitora alterações no Vault e atualiza o Qdrant.

## Indexação manual

O script:

```text
index_vault.py
```

pode ser usado para indexação completa.

## Collection

A collection padrão:

```env
QDRANT_COLLECTION=second_brain
```

## Recriar collection

Por segurança:

```env
RECREATE_COLLECTION=false
```

Para recriar explicitamente:

```env
RECREATE_COLLECTION=true
```

Use com cuidado, porque a collection existente pode ser removida antes da reconstrução.

## Parâmetros de chunking

```env
CHUNK_SIZE=1200
CHUNK_OVERLAP=200
```

Esses parâmetros controlam como textos grandes são divididos.

## Testar Qdrant

Verifique collections:

```bash
curl http://127.0.0.1:6333/collections
```

## Logs

```bash
docker logs -f second-brain-indexer
```

## Teste de busca

O repositório inclui:

```text
brain-indexer/tests/semantic_search_test.py
```

Use apenas após configurar as variáveis de ambiente adequadas.
