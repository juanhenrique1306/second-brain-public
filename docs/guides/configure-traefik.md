# Configurar Traefik

Este projeto pressupõe um Traefik já existente.

## Objetivos

- expor webhooks do n8n;
- manter o editor do n8n privado;
- usar HTTPS;
- limitar acesso por rede.

## Rede externa

O Compose usa:

```yaml
proxy:
  external: true
```

Confirme:

```bash
docker network ls
```

Se necessário:

```bash
docker network create proxy
```

## Webhook público

Exemplo de domínio:

```text
hooks.example.com
```

O router público deve encaminhar apenas caminhos necessários, como:

```text
/webhook/
/webhook-test/
```

## Editor privado

Exemplo:

```text
n8n.internal.example.com
```

Proteja com allowlist.

Exemplo:

```text
192.168.1.0/24
10.8.0.0/24
```

## NAT Docker

Em alguns cenários, o Traefik pode não enxergar o IP original do cliente VPN.

Use access logs ou `tcpdump` para descobrir o endereço real visto pelo Traefik antes de ajustar a allowlist.

Evite liberar uma faixa Docker inteira sem necessidade.
