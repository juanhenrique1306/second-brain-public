# Configurar acesso por VPN

## Objetivo

Permitir acesso ao editor privado do n8n apenas pela LAN e/ou VPN.

## Exemplo de redes

```text
LAN: 192.168.1.0/24
VPN: 10.8.0.0/24
```

No `.env`:

```env
N8N_ALLOWED_NETWORKS=192.168.1.0/24,10.8.0.0/24
```

## Confirmar IP do cliente

No Windows:

```bat
ipconfig
```

Exemplo:

```text
IPv4: 10.8.0.2
Mask: 255.255.255.0
```

Isso indica:

```text
10.8.0.0/24
```

## Se ainda houver 403

O problema pode ser NAT.

No servidor:

```bash
sudo tcpdump -ni any 'tcp dst port 443'
```

Tente acessar o n8n pela VPN e observe o IP de origem.

Em ambientes com Docker hairpin NAT, o Traefik pode enxergar um gateway Docker em vez de `10.8.0.x`.

Se precisar liberar um gateway Docker, prefira um endereço específico `/32` após confirmar exatamente qual IP chega ao Traefik.

Não use faixas amplas sem necessidade.
