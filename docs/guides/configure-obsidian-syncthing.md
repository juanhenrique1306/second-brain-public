# Configurar Obsidian e Syncthing

## Objetivo

Sincronizar o Vault do computador com o servidor.

## Fluxo

```text
Obsidian no notebook
        ↓
     Syncthing
        ↓
Vault no servidor
        ↓
Brain Indexer
```

## Notebook

Selecione a pasta usada pelo Obsidian como Vault.

Exemplo:

```text
D:\second-brain
```

## Servidor

Escolha um diretório persistente.

Exemplo:

```text
/opt/second-brain/vault
```

No projeto público, prefira paths configuráveis por variável de ambiente.

## Docker

O Vault deve ser montado dentro dos containers em:

```text
/vault
```

## Permissões

O usuário/container que executa o indexador precisa conseguir ler os arquivos.

A Brain API precisa de escrita apenas se você utilizar recursos que gravam memória diretamente no Vault.

## Segurança

Não sincronize segredos desnecessariamente.

Não publique o Vault real no GitHub.

## Teste

Crie uma nota simples no Obsidian:

```markdown
# Teste

Esta nota foi criada para validar a sincronização.
```

Confirme que ela aparece no servidor e depois nos logs do indexador.
