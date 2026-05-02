# FireManager — Referência de Comandos por Vendor

> Documento de referência: o que o agente suporta em cada fabricante.

---

## MATRIZ DE CAPACIDADES

| Operação              | SonicWall | Fortinet | pfSense | OPNsense | MikroTik | Cisco IOS | Cisco NXOS | Juniper | Aruba | Dell OS10 | Dell N | HP Comware | Ubiquiti |
|-----------------------|:---------:|:--------:|:-------:|:--------:|:--------:|:---------:|:----------:|:-------:|:-----:|:---------:|:------:|:----------:|:--------:|
| Testar conexão        | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Listar regras         | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | — | — | — | — | — | — |
| Criar regra           | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ ACL | ✓ ACL | ✓ filter | ✓ ACL | ✓ ACL | — | — | ✓ firewall |
| Editar regra          | ✓ | ✓ | ✓ | ✓ | — | — | — | — | — | — | — | — | — |
| Deletar regra         | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | — | — | — | — | — | — |
| Listar NAT            | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | — | — | — | — | — | — |
| Criar NAT             | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ static | — | — | — | — | — | — | ✓ SNAT/DNAT |
| Deletar NAT           | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | — | — | — | — | — | — |
| Listar rotas          | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Criar rota            | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Deletar rota          | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | ✓ | — | — | ✓ | — | ✓ |
| Criar grupo           | ✓ | ✓ | ✓ | ✓ | — | — | — | — | — | — | — | — | ✓ |
| Listar VLANs          | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Listar portas         | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Executar show/display | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| VLANs — criar/editar  | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ vif |
| Portas — configurar   | — | — | — | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Toggle serviços seg.  | ✓ | — | — | — | — | — | — | — | — | — | — | — | — |
| Filtro de conteúdo    | ✓ | — | — | — | — | — | — | — | — | — | — | — | — |
| Exclusões de segurança| ✓ | — | — | — | — | — | — | — | — | — | — | — | — |
| Status serviços seg.  | ✓ | — | — | — | — | — | — | — | — | — | — | — | — |

---

## COMANDOS POR VENDOR — O QUE DIGITAR NO CHAT

---

### SONICWALL (SonicOS REST + SSH)

#### Leitura
```
Liste as regras de firewall
Liste as regras da zona LAN para WAN
Liste as regras que contêm o objeto "Servers"
Liste as políticas NAT
Liste as rotas estáticas
```

#### Regras de Firewall
```
Crie uma regra permitindo tráfego da LAN 192.168.1.0/24 para 10.0.0.50 na porta 443
Crie uma regra bloqueando tráfego da zona LAN para WAN na porta 8080
Edite a regra "FM-PERMIT-HTTPS" e altere o destino para 10.0.0.100
Delete a regra "FM-PERMIT-HTTPS"
```

#### NAT
```
Crie um NAT de 192.168.1.10 para o IP público 200.1.2.3
Crie um port forwarding da porta 80 do WAN para 192.168.1.10:80
Delete o NAT "FM-NAT-WEB"
```

#### Rotas
```
Crie uma rota estática para 10.10.10.0/24 via gateway 192.168.168.2 pela interface X1
Delete a rota para 10.10.10.0/24
```

#### Serviços de Segurança (SSH CLI)
```
Ative o Gateway Antivirus
Desative o Gateway Antivirus
Ative o Intrusion Prevention
Ative o App Control
Ative o Geo-IP e bloqueie China e Russia
Ative o Botnet Filter
Ative o DPI-SSL client
Ative o DPI-SSL server e client
```

#### Filtro de Conteúdo
```
Configure um filtro de conteúdo chamado "Filtro Geral" para a zona LAN bloqueando redes sociais
Configure o filtro de conteúdo com safe search e google safe search ativados
```

#### Exclusões de Segurança
```
Adicione o IP 192.168.1.100 às exclusões do Intrusion Prevention
Adicione 10.0.0.5 às exclusões de todos os serviços de segurança
```

#### Status
```
Qual o status dos serviços de segurança?
```

---

### FORTINET (FortiOS REST)

#### Leitura
```
Liste as regras de firewall
Liste as regras da zona lan para wan
Liste as políticas NAT
Liste as rotas estáticas
```

#### Regras
```
Crie uma regra permitindo tráfego de 192.168.1.0/24 para 10.0.0.50 na porta 443
Crie uma regra bloqueando tráfego HTTP da LAN para WAN
Delete a regra "FM-PERMIT-HTTPS"
```

#### NAT / Rotas
```
Crie uma rota estática para 10.10.10.0/24 via 192.168.1.254 pela interface port2
Crie um grupo de endereços chamado "Servidores" com 192.168.1.10 e 192.168.1.20
```

---

### PFSENSE / OPNSENSE (REST API)

#### Leitura
```
Liste as regras de firewall
Liste os aliases
Liste as rotas estáticas
```

#### Regras
```
Crie uma regra permitindo TCP de qualquer origem para 192.168.1.10 na porta 443
Crie uma regra bloqueando tráfego da LAN para WAN na porta 25
Delete a regra "FM-BLOCK-SMTP"
```

#### NAT
```
Crie um port forwarding da porta 80 do WAN para 192.168.1.10:80
```

---

### MIKROTIK (RouterOS REST)

#### Leitura
```
Liste as regras de firewall
Liste as políticas NAT
Liste as rotas
```

#### Configuração
```
Crie uma regra de firewall bloqueando conexões TCP na porta 23
Crie uma rota estática para 10.10.10.0/24 via 192.168.1.254
```

---

### CISCO IOS / IOS-XE

#### Leitura
```
Liste as VLANs
Liste as portas e seus status
Liste a porta GigabitEthernet0/1
Execute o comando show running-config
Execute show ip route
Execute show interfaces status
Execute show cdp neighbors
Execute show spanning-tree
Execute show mac address-table
Execute show arp
```

#### VLANs
```
Crie a VLAN 100 com nome Cameras
Crie a VLAN 200 com nome VoIP
```

#### Portas
```
Configure a porta GigabitEthernet0/1 para acesso na VLAN 100
Configure a porta GigabitEthernet0/2 como trunk com VLANs 100 e 200
Desative a porta GigabitEthernet0/5
Reative a porta GigabitEthernet0/5
```

#### Roteamento / ACL
```
Crie uma rota estática para 10.10.10.0 255.255.255.0 via 192.168.1.254
Crie uma ACL permitindo TCP de 192.168.1.0/24 para 10.0.0.50 na porta 443
Configure NAT estático de 192.168.1.10 para 200.1.2.3
```

#### STP
```
Ative o modo RSTP no switch
Ative o BPDU Guard global
Configure portfast na porta GigabitEthernet0/1
```

---

### CISCO NX-OS (Nexus)

#### Leitura
```
Liste as VLANs
Liste as interfaces e seus status
Execute show vpc
Execute show interface status
Execute show ip route
```

#### VLANs / Interfaces
```
Crie a VLAN 100 com nome Cameras
Configure a interface Vlan100 com IP 192.168.100.1/24
Configure a interface Ethernet1/1 para acesso na VLAN 100
Habilite a feature vpc
```

#### Roteamento
```
Crie uma rota estática para 10.10.10.0/24 via 192.168.1.254
```

---

### JUNIPER JunOS

#### Leitura
```
Liste as VLANs
Liste as interfaces
Execute show route
Execute show arp
Execute show spanning-tree interface
Execute show lldp neighbors
```

#### VLANs
```
Crie a VLAN Cameras com ID 100
Configure a interface ge-0/0/1 para acesso na VLAN Cameras
Configure a interface ge-0/0/2 como trunk com as VLANs Cameras e VoIP
```

#### Portas
```
Desative a interface ge-0/0/5
Reative a interface ge-0/0/5
Configure a interface irb.100 com IP 192.168.100.1/24
```

#### Roteamento / Firewall
```
Crie uma rota estática para 10.10.10.0/24 via 192.168.1.254
Crie uma rota padrão via 192.168.1.254
Configure o RSTP no switch
```

---

### ARUBA OS-CX

#### Leitura
```
Liste as VLANs
Liste as portas
Liste a porta 1/1/1
Execute show running-config
Execute show lldp neighbors
Execute show spanning-tree
```

#### VLANs / Portas
```
Crie a VLAN 100 com nome Cameras
Configure a porta 1/1/1 para acesso na VLAN 100
Configure a porta 1/1/2 como trunk com VLANs 100 e 200 e nativa 1
Configure a porta 1/1/3 com dados na VLAN 100 e voz na VLAN 200
Desative a porta 1/1/5
```

#### Roteamento / LAG
```
Crie uma rota estática para 10.10.10.0/24 via 192.168.1.254
Configure um LAG entre as portas 1/1/1 e 1/1/2
Configure a interface VLAN 100 com IP 192.168.100.1/24 e DHCP relay para 10.0.0.1
```

---

### DELL OS10 (PowerSwitch S/Z series)

#### Leitura
```
Liste as VLANs
Liste as interfaces e seus status
Execute show running-config
Execute show ip route
Execute show spanning-tree
Execute show lldp neighbors
```

#### VLANs / Portas
```
Crie a VLAN 100 com nome Cameras
Configure a interface ethernet 1/1/1 para acesso na VLAN 100
Configure a interface ethernet 1/1/2 como trunk com VLANs 100 e 200
Desative a interface ethernet 1/1/5
```

#### Roteamento
```
Crie uma rota estática para 10.10.10.0/24 via 192.168.1.254
Configure a interface VLAN 100 com IP 192.168.100.1/24
```

---

### DELL N-SERIES DNOS6 (N1524P, N1548P, N2000, N3000)

#### Leitura
```
Liste as VLANs
Liste as portas e seus status
Liste a porta 1
Liste a porta Te1/0/1
Execute show running-config
Execute show spanning-tree
Execute show lldp neighbors
Execute show mac address-table
Execute show arp
Execute show ip route
Execute show power inline
Execute show snmp
Execute show sntp status
Execute show logging
Execute show inventory
Execute show interfaces counters
```

#### VLANs
```
Crie a VLAN 100 com nome GERENCIA
Crie a VLAN 200 com nome CFTV
Crie as VLANs 100, 200 e 300 de uma vez
Renomeie a VLAN 100 para GERENCIA-NOVA
Delete a VLAN 999
```

#### Portas — Acesso
```
Configure a porta 5 para acesso na VLAN 100
Configure a porta 15 como câmera na VLAN 200
Mude a VLAN da porta 5 para 200
Mude a descrição da porta 5 para IMPRESSORA-01
Desative a porta 40
Reative a porta 40
```

#### Portas — General (VoIP + Dados)
```
Configure a porta 2 no modo general com VLAN de dados 100 e VoIP 300 tagged
Configure a porta 10 como AP com VLAN de gerência 8 nativa e VLANs 100 e 200 tagged
Adicione a VLAN 400 tagged na porta 3
Remova a VLAN 400 da porta 3
```

#### Portas — Trunk (Uplinks)
```
Configure a porta Te1/0/1 como uplink trunk com VLANs 2,3,8,100,200
Configure a porta Gi1/0/48 como uplink para o core com VLANs 100 e 200
Adicione a VLAN 300 ao trunk da porta Te1/0/1
Remova a VLAN 300 do trunk da porta Te1/0/1
```

#### PoE
```
Ative o PoE na porta 5
Desative o PoE na porta 10
Limite o PoE da porta 5 a 15.4 watts
```

#### Roteamento / DHCP
```
Configure o gateway padrão para 10.100.0.1
Crie uma rota estática para 192.168.50.0/24 via 10.100.0.1
Configure o DHCP relay na VLAN 8 para os servidores 172.16.2.220 e 172.16.0.74
Remova o ip helper-address 172.16.2.221 da VLAN 8
```

#### Sistema
```
Altere o hostname para SW-PRODUCAO
Configure o servidor de logs 172.16.2.69
Configure o servidor SNMP com community Public_Test para o host 172.16.2.70
Configure os servidores NTP 172.16.2.220 e 172.16.2.221
```

#### STP
```
Ative o modo RSTP
Ative a proteção BPDU global
```

---

### HP / H3C COMWARE 5.x (V1910, V3600, V5800)

#### Leitura
```
Liste as VLANs
Liste as interfaces
Liste a porta 1
Execute display current-configuration
Execute display arp
Execute display ip routing-table
Execute display stp brief
Execute display lldp neighbor-information list
Execute display version
Execute ping 8.8.8.8
```

#### VLANs
```
Crie a VLAN 100 com nome GERENCIA
Crie as VLANs 100 e 200 com nomes GERENCIA e CFTV
```

#### Portas
```
Configure a porta 5 para acesso na VLAN 100
Configure a porta 28 como uplink trunk com VLANs 2, 3, 100 e 200
Configure a porta 3 como hybrid para AP com VLAN 8 nativa e VLANs 100, 200 tagged
Desative a porta 10
Reative a porta 10
```

#### Roteamento
```
Crie uma rota padrão via 10.100.0.1
Crie uma rota estática para 10.10.10.0/24 via 192.168.1.254
Configure a interface VLAN 100 com IP 10.100.1.60/23
```

#### STP
```
Ative o RSTP
Ative a proteção BPDU global
```

---

### UBIQUITI EDGEOS / EDGEROUTER

#### Leitura
```
Liste as VLANs
Liste as interfaces
Execute show ip route
Execute show arp
Execute show firewall
Execute show nat
```

#### Interfaces / VLANs
```
Configure a subinterface eth1 com VLAN 100 e IP 192.168.100.1/24
Configure a descrição da interface eth1 como LAN
Desative a interface eth1
```

#### Roteamento
```
Crie uma rota estática para 10.10.10.0/24 via 192.168.1.254
Crie uma rota padrão via 192.168.1.254
```

#### Firewall / NAT
```
Crie uma regra de firewall permitindo TCP de 192.168.1.0/24 para 10.0.0.50 porta 443
Configure NAT masquerade para a interface eth0 da rede 192.168.1.0/24
Configure port forwarding da porta 80 do WAN para 192.168.1.10:80
```

#### DHCP
```
Configure o DHCP relay na interface eth1 para o servidor 10.0.0.1
```

---

---

# CADERNO DE TESTES — FireManager SSH/REST Connectors

> **Objetivo:** Validar sistematicamente cada conector de vendor no ambiente real, em três fases progressivas de risco.
>
> **Fases:**
> - **Fase 1 — Conectividade:** Apenas testa a autenticação SSH/REST. Risco zero.
> - **Fase 2 — Leitura:** Comandos read-only (show/display/list). Risco zero.
> - **Fase 3 — Escrita:** Cria objeto de teste, verifica, depois remove. Risco baixo (objeto controlado).
>
> **VLAN de teste padrão:** VLAN 999 (nome: `FM-TEST`). Escolha um número que não exista na rede.
>
> **Como executar:**
> 1. Selecione o dispositivo no FireManager.
> 2. Digite o comando exatamente como indicado no campo "Comando no chat".
> 3. Aguarde o agente gerar e executar o plano.
> 4. Verifique o resultado conforme indicado.
> 5. Marque ✅ ou ❌ na coluna "Resultado".

---

## LEGENDA DE COLUNAS

| Campo | Descrição |
|---|---|
| **ID** | Identificador único do teste |
| **Fase** | 1=Conectividade, 2=Leitura, 3=Escrita |
| **Risco** | Zero / Baixo |
| **Comando** | O que digitar no chat do FireManager |
| **Esperado** | O que o agente deve produzir/executar |
| **Verificação** | Como confirmar que funcionou |
| **Passou se** | Critério de sucesso |
| **Falhou se** | Sintoma de falha + provável causa |

---

---

## SONICWALL

> Requer: dispositivo SonicWall com credenciais REST (token) e/ou SSH configuradas.

---

### SW-01 — Testar conexão REST
**Fase:** 1 | **Risco:** Zero

**Comando no chat:**
```
Teste a conexão com o dispositivo
```
**Esperado:** Agente chama `test_connection` via REST, obtém versão do firmware.

**Verificação:** Resposta contém versão SonicOS (ex: `7.0.1-5035`).

**✅ Passou se:** Campo "Firmware" aparece na resposta e status é "Conectado".

**❌ Falhou se:** "Connection refused" → porta/SSL errado; "401 Unauthorized" → token inválido.

---

### SW-02 — Listar regras de firewall
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste todas as regras de firewall
```
**Esperado:** Agente chama `list_rules`, retorna JSON com lista de políticas.

**Verificação:** Resposta lista regras com campos `name`, `action`, `src_zone`, `dst_zone`.

**✅ Passou se:** Pelo menos uma regra listada (ou "nenhuma regra encontrada" se vazio).

**❌ Falhou se:** Erro 500 ou timeout → API endpoint incorreto; erro de parsing → firmware incompatível.

---

### SW-03 — Criar regra de firewall (TESTE — remover depois)
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Crie uma regra bloqueando tráfego TCP da LAN para WAN na porta 65432 com nome FM-TEST-BLOCK
```
**Esperado:** Agente gera plano `create_rule` com action=deny, dst_port=65432, nome=FM-TEST-BLOCK.

**Verificação:** Liste as regras → regra "FM-TEST-BLOCK" aparece na lista.

**✅ Passou se:** Regra aparece na listagem com action=deny e porta 65432.

**❌ Falhou se:** Erro 400 → nome duplicado (já existe regra com esse nome); timeout → REST não responde.

---

### SW-04 — Deletar regra de teste
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Delete a regra FM-TEST-BLOCK
```
**Esperado:** Agente gera plano `delete_rule`, chama DELETE /api/sonicos/v1/access-rules/{uuid}.

**Verificação:** Liste as regras → "FM-TEST-BLOCK" não aparece mais.

**✅ Passou se:** Regra removida da listagem.

**❌ Falhou se:** Erro 404 → uuid não resolvido corretamente (bug no lookup por nome).

---

### SW-05 — Status dos serviços de segurança (SSH)
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Qual o status dos serviços de segurança?
```
**Esperado:** Agente usa intent `get_security_status`, conecta via SSH CLI, executa comando de status.

**Verificação:** Resposta mostra estado (ativo/inativo) de Gateway AV, IPS, App Control, Geo-IP, Botnet.

**✅ Passou se:** Pelo menos 3 serviços listados com status.

**❌ Falhou se:** "SSH connection refused" → porta SSH fechada; "Authentication failed" → credenciais SSH não preenchidas.

---

### SW-06 — Ativar serviço de segurança (SSH)
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Ative o Botnet Filter
```
**Esperado:** Agente gera plano `toggle_botnet`, conecta SSH, executa sequência de comandos CLI.

**Verificação:** Repita SW-05 → Botnet Filter aparece como "Enabled".

**✅ Passou se:** Status muda para ativo sem erro CLI.

**❌ Falhou se:** Sequência de comandos retorna "%" prompt de erro → versão SonicOS não suporta esse comando via CLI.

---

---

## FORTINET

> Requer: FortiGate com token de API (perfil com permissão de leitura/escrita).

---

### FG-01 — Testar conexão
**Fase:** 1 | **Risco:** Zero

**Comando no chat:**
```
Teste a conexão com o dispositivo
```
**Verificação:** Resposta contém versão FortiOS (ex: `v7.4.3`).

**✅ Passou se:** Status "Conectado" com firmware visível.

**❌ Falhou se:** "SSL: CERTIFICATE_VERIFY_FAILED" → desative verify_ssl no dispositivo ou importe o certificado; "401" → token sem permissão.

---

### FG-02 — Listar regras
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste as políticas de firewall
```
**Verificação:** Lista com policyid, name, srcintf, dstintf, action.

**✅ Passou se:** Lista retorna (pode ser vazia se novo equipamento).

**❌ Falhou se:** "403 Forbidden" → token sem permissão de leitura em `firewall/policy`.

---

### FG-03 — Criar rota de teste
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Crie uma rota estática para 192.0.2.0/24 via 192.168.1.254 pela interface port2 com nome FM-TEST
```
**Verificação:** Liste as rotas → 192.0.2.0/24 aparece (192.0.2.0/24 é bloco de documentação RFC 5737, seguro para teste).

**✅ Passou se:** Rota visível na listagem.

**❌ Falhou se:** Interface `port2` não existe → ajuste o nome da interface para a real do equipamento.

---

### FG-04 — Deletar rota de teste
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Delete a rota para 192.0.2.0/24
```
**✅ Passou se:** Rota não aparece mais na listagem.

---

---

## PFSENSE / OPNSENSE

> pfSense requer plugin `pfsense-api`. OPNsense usa API nativa com chave+segredo.

---

### PF-01 — Testar conexão
**Fase:** 1 | **Risco:** Zero

**Comando no chat:**
```
Teste a conexão com o dispositivo
```
**✅ Passou se:** Versão pfSense/OPNsense retornada (ex: `2.7.2`).

**❌ Falhou se:** "404 Not Found" → plugin pfsense-api não instalado; OPNsense: "401" → chave/segredo errado.

---

### PF-02 — Listar aliases
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste os aliases
```
**✅ Passou se:** Lista de aliases retornada (pode ser vazia).

---

### PF-03 — Criar e remover regra de teste
**Fase:** 3 | **Risco:** Baixo

**Comando:**
```
Crie uma regra bloqueando TCP da LAN para qualquer destino na porta 65432
```
Depois:
```
Delete a regra que bloqueia a porta 65432
```
**✅ Passou se:** Regra criada e removida sem erro.

---

---

## MIKROTIK

> Requer: RouterOS REST API habilitada (`/ip/service enable www-ssl` ou `www`).

---

### MT-01 — Testar conexão
**Fase:** 1 | **Risco:** Zero

**Comando no chat:**
```
Teste a conexão com o dispositivo
```
**✅ Passou se:** Versão RouterOS retornada.

**❌ Falhou se:** "Connection refused" → API REST não habilitada. Execute no terminal MikroTik: `/ip/service/set www enabled=yes`.

---

### MT-02 — Listar regras NAT
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste as políticas NAT
```
**✅ Passou se:** Lista de regras NAT (src-nat/dst-nat).

---

### MT-03 — Criar e remover rota de teste
**Fase:** 3 | **Risco:** Baixo

**Comando:**
```
Crie uma rota estática para 192.0.2.0/24 via 192.168.1.254
```
Depois:
```
Delete a rota para 192.0.2.0/24
```
**✅ Passou se:** Rota criada e removida sem erro.

---

---

## CISCO IOS / IOS-XE

> Requer: Switch/roteador com SSH habilitado, enable secret configurado nas credenciais.

---

### IOS-01 — Testar conexão SSH
**Fase:** 1 | **Risco:** Zero

**Comando no chat:**
```
Teste a conexão com o dispositivo
```
**Esperado:** Agente conecta via SSH, executa `show version`.

**Verificação:** Versão IOS visível na resposta (ex: `15.2(7)E5` ou `17.3.6`).

**✅ Passou se:** Output de `show version` presente.

**❌ Falhou se:** "Authentication failed" → verifique username/password/enable secret; "Pattern not detected" → timeout, verifique `terminal length 0` (base connector envia automaticamente).

---

### IOS-02 — Listar VLANs
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste as VLANs
```
**Esperado:** Agente executa `show vlan brief`, retorna tabela de VLANs.

**Verificação:** VLANs 1 e qualquer outra configurada aparecem na lista.

**✅ Passou se:** Tabela com ID, Name, Status, Ports.

**❌ Falhou se:** "Invalid input detected" → dispositivo pode ser roteador sem suporte a VLANs.

---

### IOS-03 — Listar portas
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste as portas e seus status
```
**Esperado:** Agente executa `show interfaces status`, retorna tabela de portas.

**✅ Passou se:** Lista de interfaces com estado connected/notconnect/disabled.

---

### IOS-04 — Criar VLAN de teste
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Crie a VLAN 999 com nome FM-TEST
```
**Esperado:** Agente entra em config mode, executa `vlan 999` + `name FM-TEST` + `end` + `write memory`.

**Verificação:** `Liste as VLANs` → VLAN 999 FM-TEST aparece.

**✅ Passou se:** VLAN 999 visível com nome FM-TEST.

**❌ Falhou se:** VLAN aparece sem nome → `name` não foi executado; "Invalid input" → VLAN 999 em uso ou reservada.

---

### IOS-05 — Configurar porta de acesso (TESTE)
**Fase:** 3 | **Risco:** Baixo

**Pré-requisito:** IOS-04 concluído. Use uma porta sem uso (confirme antes).

**Comando no chat:**
```
Configure a porta GigabitEthernet0/10 para acesso na VLAN 999
```
**Verificação:** `show interfaces GigabitEthernet0/10 switchport` → Access Mode VLAN: 999.

**✅ Passou se:** VLAN de acesso = 999 na porta.

**❌ Falhou se:** "Interface not found" → ajuste o nome da interface para o existente no equipamento.

---

### IOS-06 — Remover VLAN de teste
**Fase:** 3 | **Risco:** Baixo

**Pré-requisito:** Mova a porta de volta para VLAN original antes.

**Comando no chat:**
```
Delete a VLAN 999
```
**Verificação:** `Liste as VLANs` → VLAN 999 não aparece.

**✅ Passou se:** VLAN 999 removida.

---

---

## CISCO NX-OS (NEXUS)

> Requer: Nexus com SSH habilitado. `feature ssh` deve estar ativo.

---

### NX-01 — Testar conexão
**Fase:** 1 | **Risco:** Zero

**Comando no chat:**
```
Teste a conexão com o dispositivo
```
**✅ Passou se:** Versão NX-OS visível (ex: `9.3(10)`).

**❌ Falhou se:** "Authentication failed" → NX-OS usa username/password, sem enable; "Timeout" → `feature ssh` não habilitada.

---

### NX-02 — Listar VLANs
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste as VLANs
```
**✅ Passou se:** Tabela de VLANs com estado (active/suspend).

---

### NX-03 — Criar e remover VLAN de teste
**Fase:** 3 | **Risco:** Baixo

**Comando:**
```
Crie a VLAN 999 com nome FM-TEST
```
Depois:
```
Delete a VLAN 999
```
**✅ Passou se:** VLAN criada e removida.

**❌ Falhou se:** "not a feature" → feature vlan não habilitada. Execute: `feature vlan`.

---

---

## JUNIPER JUNOS

> Requer: Switch/roteador Juniper com SSH + netconf ou SSH CLI. Netmiko usa SSH CLI.

---

### JNP-01 — Testar conexão
**Fase:** 1 | **Risco:** Zero

**Comando no chat:**
```
Teste a conexão com o dispositivo
```
**Esperado:** `show version` via SSH.

**✅ Passou se:** Versão Junos visível (ex: `22.2R1.9`).

**❌ Falhou se:** "Pattern not detected" → prompt JunOS diferente do esperado; "Authentication failed" → credenciais erradas.

---

### JNP-02 — Listar VLANs
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste as VLANs
```
**Esperado:** Agente executa `show vlans`.

**✅ Passou se:** Lista de VLANs com nome e membros de interface.

---

### JNP-03 — Executar show de roteamento
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Execute show route
```
**✅ Passou se:** Tabela de roteamento retornada.

---

### JNP-04 — Criar VLAN de teste com commit
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Crie a VLAN FM-TEST com ID 999
```
**Esperado:** Agente entra em `configure`, executa `set vlans FM-TEST vlan-id 999`, faz `commit`.

**Verificação:** `show vlans FM-TEST` → VLAN visível.

**✅ Passou se:** VLAN FM-TEST presente após commit.

**❌ Falhou se:** "commit failed" → conflito de configuração; rollback aplicado automaticamente pelo conector.

---

### JNP-05 — Remover VLAN de teste
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Delete a VLAN FM-TEST
```
**Esperado:** `delete vlans FM-TEST` + `commit`.

**✅ Passou se:** VLAN não aparece mais em `show vlans`.

---

---

## ARUBA OS-CX

> Requer: Switch Aruba CX com SSH habilitado.

---

### ARB-01 — Testar conexão
**Fase:** 1 | **Risco:** Zero

**Comando no chat:**
```
Teste a conexão com o dispositivo
```
**✅ Passou se:** Versão ArubaOS-CX visível.

---

### ARB-02 — Listar VLANs
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste as VLANs
```
**✅ Passou se:** Tabela de VLANs com ID, nome, estado.

---

### ARB-03 — Listar portas
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste as portas e seus status
```
**✅ Passou se:** Lista de interfaces com link state e VLAN.

---

### ARB-04 — Criar VLAN de teste
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Crie a VLAN 999 com nome FM-TEST
```
**Verificação:** `show vlan 999`.

**✅ Passou se:** VLAN 999 FM-TEST presente.

---

### ARB-05 — Configurar porta de acesso (TESTE)
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Configure a porta 1/1/48 para acesso na VLAN 999
```
**Verificação:** `show interface 1/1/48` → VLAN de acesso 999.

**✅ Passou se:** Porta movida para VLAN 999.

**Observação:** Use uma porta sem uso ou ajuste o número para porta disponível.

---

### ARB-06 — Remover VLAN de teste
**Fase:** 3 | **Risco:** Baixo

**Pré-requisito:** Reverta a porta antes de remover a VLAN.

**Comando no chat:**
```
Delete a VLAN 999
```
**✅ Passou se:** VLAN 999 não aparece mais.

---

---

## DELL OS10 (POWERSWITCH)

> Requer: Switch Dell PowerSwitch S/Z com SSH habilitado.

---

### D10-01 — Testar conexão
**Fase:** 1 | **Risco:** Zero

**Comando no chat:**
```
Teste a conexão com o dispositivo
```
**✅ Passou se:** Versão Dell OS10 visível.

**❌ Falhou se:** Device type incorreto → verifique campo `os_version` nas credenciais (deve conter "OS10" ou deixar padrão).

---

### D10-02 — Listar VLANs
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste as VLANs
```
**✅ Passou se:** Lista de VLANs retornada.

---

### D10-03 — Criar e remover VLAN de teste
**Fase:** 3 | **Risco:** Baixo

**Comando:**
```
Crie a VLAN 999 com nome FM-TEST
```
Depois:
```
Delete a VLAN 999
```
**✅ Passou se:** VLAN criada e removida.

---

---

## DELL N-SERIES — DNOS6

> Requer: Switch Dell N com SSH habilitado e enable password configurado.
> **Atenção:** Este conector usa autenticação apenas por senha (sem keyboard-interactive). O campo `enable_password` deve estar preenchido nas credenciais.

---

### DN-01 — Testar conexão SSH
**Fase:** 1 | **Risco:** Zero

**Comando no chat:**
```
Teste a conexão com o dispositivo
```
**Esperado:** Conector conecta via SSH, entra em modo enable, executa `show version`.

**Verificação:** Output contém modelo (ex: `N2048P`) e versão DNOS6 (ex: `6.3.x.x`).

**✅ Passou se:** Firmware visível na resposta.

**❌ Falhou se:**
- "Authentication failed" → password SSH incorreto
- "Unable to enter enable mode" → enable password incorreto nas credenciais
- "Pattern not detected" → conector não reconhece o prompt; verifique se o hostname do switch bate com o esperado pelo Netmiko

---

### DN-02 — Listar VLANs
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste as VLANs
```
**Esperado:** Agente executa `show vlan`, retorna tabela.

**Verificação:** VLAN 1 deve aparecer. Outras VLANs configuradas também.

**✅ Passou se:** Tabela com VLAN ID, Name, Status, Ports retornada.

**❌ Falhou se:** "Pattern not detected" com timeout → paging não foi desabilitado. Verifique se `terminal length 0` é enviado após `enable()` no conector DellNConnector.

---

### DN-03 — Listar portas
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste as portas e seus status
```
**Esperado:** Agente executa `show interfaces status`.

**Verificação:** Lista de interfaces Gi1/0/x e Te1/0/x com estado (Up/Down).

**✅ Passou se:** Lista de portas retornada sem timeout.

**❌ Falhou se:** Timeout em porta específica → output longo; `read_timeout=90` deve ser suficiente.

---

### DN-04 — Inspecionar porta específica
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste a porta 1
```
**Esperado:** Agente executa `show interfaces Gi1/0/1` (mapeamento numérico → Gi1/0/X).

**Verificação:** Detalhes da porta: descrição, VLAN, velocidade, estado, PoE.

**✅ Passou se:** Output de `show interfaces Gi1/0/1` retornado corretamente.

**❌ Falhou se:** "Pattern not detected: 'SW2\\-DIS\\-TI\\-RACK\\#'" → bug de paging retornou; confirme que a versão do `dell_n.py` tem `terminal length 0` após `enable()`.

---

### DN-05 — Executar show personalizado
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Execute show power inline
```
**Verificação:** Tabela PoE por porta com estado e wattagem.

**✅ Passou se:** Output sem "%" de erro e sem truncamento.

---

### DN-06 — Criar VLAN de teste
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Crie a VLAN 999 com nome FM-TEST
```
**Esperado:** Agente executa:
```
vlan database
vlan 999
exit
interface vlan 999
name FM-TEST
exit
write memory
```
**Verificação:** `Liste as VLANs` → VLAN 999 FM-TEST visível.

**✅ Passou se:** VLAN 999 aparece na listagem com nome FM-TEST.

**❌ Falhou se:** VLAN criada sem nome → sequência `interface vlan 999 / name` não executada; revise o prompt do vendor DNOS6.

---

### DN-07 — Configurar porta de acesso (TESTE)
**Fase:** 3 | **Risco:** Baixo

**Pré-requisito:** DN-06 concluído. Use uma porta sem uso.

**Comando no chat:**
```
Configure a porta 48 para acesso na VLAN 999
```
**Esperado:**
```
interface gi1/0/48
switchport mode access
switchport access vlan 999
description FM-TEST
exit
write memory
```
**Verificação:** `show interfaces gi1/0/48 switchport` → Access Mode VLAN: 999.

**✅ Passou se:** Porta em VLAN 999 modo access.

---

### DN-08 — Configurar porta trunk de uplink (TESTE)
**Fase:** 3 | **Risco:** Baixo

**Pré-requisito:** Use uma porta de uplink inativa ou uma porta Te.

**Comando no chat:**
```
Configure a porta Te1/0/1 como uplink trunk com VLANs 100, 200 e 999
```
**Esperado:**
```
interface te1/0/1
switchport mode trunk
switchport trunk allowed vlan 100,200,999
exit
write memory
```
**Verificação:** `show interfaces te1/0/1 switchport` → modo trunk, VLANs 100,200,999 permitidas.

**✅ Passou se:** Modo trunk e VLANs corretas.

---

### DN-09 — Remover VLAN de teste
**Fase:** 3 | **Risco:** Baixo

**Pré-requisito:** Reverta as portas para VLANs originais antes.

**Comando no chat:**
```
Delete a VLAN 999
```
**Esperado:**
```
vlan database
no vlan 999
exit
write memory
```
**Verificação:** `Liste as VLANs` → VLAN 999 não aparece.

**✅ Passou se:** VLAN removida.

**❌ Falhou se:** "VLAN 999 still in use" → ainda há portas em access VLAN 999. Mova as portas primeiro.

---

---

## HP / H3C COMWARE 5.x

> Requer: Switch H3C/HP com SSH habilitado e **Senha cmdline-mode** preenchida nas credenciais.
> Sem essa senha, nenhum comando funciona — o conector rejeita antes de conectar.

---

### HPC-01 — Testar conexão e cmdline-mode
**Fase:** 1 | **Risco:** Zero

**Comando no chat:**
```
Teste a conexão com o dispositivo
```
**Esperado:** Conector conecta via SSH, executa `_cmdline-mode on` + senha, depois `display version`.

**Verificação:** Output contém modelo H3C/HP e versão Comware (ex: `Comware Software, Version 5.20`).

**✅ Passou se:** Versão Comware visível.

**❌ Falhou se:**
- "HP Comware requer 'Senha cmdline-mode'" → campo não preenchido nas credenciais do dispositivo
- "Wrong password" no cmdline-mode → senha incorreta (padrão fábrica: `512900`)
- "Pattern not detected" → hostname do switch diferente do base_prompt detectado

---

### HPC-02 — Listar VLANs
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste as VLANs
```
**Esperado:** Agente executa `display vlan all`.

**Verificação:** Lista com VLAN ID, nome, portas tagged/untagged.

**✅ Passou se:** VLANs retornadas (VLAN 1 pelo menos).

**❌ Falhou se:** "---- More ----" truncando output → `_comware_send_display()` deve enviar espaços para paginar. Verifique se `display vlan all` é tratado com `_comware_send_display`.

---

### HPC-03 — Listar interfaces
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste as interfaces
```
**Esperado:** Agente executa `display interface` ou `display interface brief`.

**Atenção:** `display interface brief` **NÃO existe** no HP 1910. O agente deve usar `display interface`.

**✅ Passou se:** Output de interfaces retornado sem erro "% Unknown command".

**❌ Falhou se:** "% Unknown command" com `display interface brief` → o prompt do vendor HP Comware deve proibir esse comando; revise `hp_comware.txt`.

---

### HPC-04 — Executar ping (diagnóstico)
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Execute ping 8.8.8.8
```
**Esperado:** Agente executa `ping 8.8.8.8` com tratamento de paging.

**✅ Passou se:** Output do ping com estatísticas de pacotes.

---

### HPC-05 — Criar VLAN de teste
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Crie a VLAN 999 com nome FM-TEST
```
**Esperado:** Agente entra em system-view, executa:
```
vlan 999
 name FM-TEST
 quit
```
Depois `save force`.

**Verificação:** `display vlan 999` → VLAN 999 com nome FM-TEST.

**✅ Passou se:** VLAN presente e nomeada.

---

### HPC-06 — Configurar porta de acesso (TESTE)
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Configure a porta 24 para acesso na VLAN 999
```
**Esperado:**
```
interface GigabitEthernet1/0/24
 port link-type access
 port access vlan 999
 quit
```
**✅ Passou se:** `display interface GigabitEthernet1/0/24` mostra PVID=999 e link-type=access.

---

### HPC-07 — Remover VLAN de teste
**Fase:** 3 | **Risco:** Baixo

**Pré-requisito:** Reverta a porta antes.

**Comando no chat:**
```
Delete a VLAN 999
```
**Esperado:**
```
undo vlan 999
```
**✅ Passou se:** `display vlan 999` retorna "VLAN 999 does not exist".

---

---

## UBIQUITI EDGEOS / EDGEROUTER

> Requer: EdgeRouter com SSH habilitado. Netmiko device type: `ubiquiti_edgerouter`.

---

### UBQ-01 — Testar conexão
**Fase:** 1 | **Risco:** Zero

**Comando no chat:**
```
Teste a conexão com o dispositivo
```
**✅ Passou se:** Versão EdgeOS visível (ex: `v2.0.9`).

**❌ Falhou se:** "Pattern not detected" → prompt diferente do esperado pelo Netmiko; `ubiquiti_edgerouter` usa `$` como prompt.

---

### UBQ-02 — Listar interfaces
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Liste as interfaces
```
**✅ Passou se:** Lista de interfaces eth/vtun com IPs e estados.

---

### UBQ-03 — Executar show de roteamento
**Fase:** 2 | **Risco:** Zero

**Comando no chat:**
```
Execute show ip route
```
**✅ Passou se:** Tabela de rotas retornada.

---

### UBQ-04 — Criar rota de teste
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Crie uma rota estática para 192.0.2.0/24 via 192.168.1.254
```
**Verificação:** `show ip route` → 192.0.2.0/24 visível como rota estática.

**✅ Passou se:** Rota presente após commit.

---

### UBQ-05 — Remover rota de teste
**Fase:** 3 | **Risco:** Baixo

**Comando no chat:**
```
Delete a rota para 192.0.2.0/24
```
**✅ Passou se:** Rota não aparece mais.

---

---

## CHECKLIST DE EXECUÇÃO

Copie esta tabela para o seu controle de testes. Marque ✅ (passou), ❌ (falhou) ou ⏭ (pulado/não aplicável).

| ID | Vendor | Teste | Fase | Resultado | Observação |
|---|---|---|---|---|---|
| SW-01 | SonicWall | Testar conexão REST | 1 | | |
| SW-02 | SonicWall | Listar regras | 2 | | |
| SW-03 | SonicWall | Criar regra FM-TEST-BLOCK | 3 | | |
| SW-04 | SonicWall | Deletar regra FM-TEST-BLOCK | 3 | | |
| SW-05 | SonicWall | Status serviços (SSH) | 2 | | |
| SW-06 | SonicWall | Ativar Botnet Filter | 3 | | |
| FG-01 | Fortinet | Testar conexão | 1 | | |
| FG-02 | Fortinet | Listar regras | 2 | | |
| FG-03 | Fortinet | Criar rota de teste | 3 | | |
| FG-04 | Fortinet | Deletar rota de teste | 3 | | |
| PF-01 | pfSense/OPNsense | Testar conexão | 1 | | |
| PF-02 | pfSense/OPNsense | Listar aliases | 2 | | |
| PF-03 | pfSense/OPNsense | Criar/remover regra | 3 | | |
| MT-01 | MikroTik | Testar conexão | 1 | | |
| MT-02 | MikroTik | Listar NAT | 2 | | |
| MT-03 | MikroTik | Criar/remover rota | 3 | | |
| IOS-01 | Cisco IOS | Testar conexão SSH | 1 | | |
| IOS-02 | Cisco IOS | Listar VLANs | 2 | | |
| IOS-03 | Cisco IOS | Listar portas | 2 | | |
| IOS-04 | Cisco IOS | Criar VLAN 999 | 3 | | |
| IOS-05 | Cisco IOS | Configurar porta acesso | 3 | | |
| IOS-06 | Cisco IOS | Remover VLAN 999 | 3 | | |
| NX-01 | Cisco NXOS | Testar conexão | 1 | | |
| NX-02 | Cisco NXOS | Listar VLANs | 2 | | |
| NX-03 | Cisco NXOS | Criar/remover VLAN | 3 | | |
| JNP-01 | Juniper | Testar conexão | 1 | | |
| JNP-02 | Juniper | Listar VLANs | 2 | | |
| JNP-03 | Juniper | Executar show route | 2 | | |
| JNP-04 | Juniper | Criar VLAN com commit | 3 | | |
| JNP-05 | Juniper | Remover VLAN | 3 | | |
| ARB-01 | Aruba | Testar conexão | 1 | | |
| ARB-02 | Aruba | Listar VLANs | 2 | | |
| ARB-03 | Aruba | Listar portas | 2 | | |
| ARB-04 | Aruba | Criar VLAN 999 | 3 | | |
| ARB-05 | Aruba | Configurar porta acesso | 3 | | |
| ARB-06 | Aruba | Remover VLAN 999 | 3 | | |
| D10-01 | Dell OS10 | Testar conexão | 1 | | |
| D10-02 | Dell OS10 | Listar VLANs | 2 | | |
| D10-03 | Dell OS10 | Criar/remover VLAN | 3 | | |
| DN-01 | Dell N-Series | Testar conexão SSH | 1 | | |
| DN-02 | Dell N-Series | Listar VLANs | 2 | | |
| DN-03 | Dell N-Series | Listar portas | 2 | | |
| DN-04 | Dell N-Series | Inspecionar porta 1 | 2 | | |
| DN-05 | Dell N-Series | show power inline | 2 | | |
| DN-06 | Dell N-Series | Criar VLAN 999 | 3 | | |
| DN-07 | Dell N-Series | Configurar porta acesso | 3 | | |
| DN-08 | Dell N-Series | Configurar trunk | 3 | | |
| DN-09 | Dell N-Series | Remover VLAN 999 | 3 | | |
| HPC-01 | HP Comware | Testar conexão + cmdline | 1 | | |
| HPC-02 | HP Comware | Listar VLANs | 2 | | |
| HPC-03 | HP Comware | Listar interfaces | 2 | | |
| HPC-04 | HP Comware | Executar ping | 2 | | |
| HPC-05 | HP Comware | Criar VLAN 999 | 3 | | |
| HPC-06 | HP Comware | Configurar porta acesso | 3 | | |
| HPC-07 | HP Comware | Remover VLAN 999 | 3 | | |
| UBQ-01 | Ubiquiti | Testar conexão | 1 | | |
| UBQ-02 | Ubiquiti | Listar interfaces | 2 | | |
| UBQ-03 | Ubiquiti | show ip route | 2 | | |
| UBQ-04 | Ubiquiti | Criar rota de teste | 3 | | |
| UBQ-05 | Ubiquiti | Deletar rota de teste | 3 | | |

---

## GUIA DE DIAGNÓSTICO RÁPIDO

| Sintoma | Causa Provável | Ação |
|---|---|---|
| "Authentication failed" | Usuário/senha errados | Verifique credenciais no dispositivo |
| "Unable to enter enable mode" | Enable secret incorreto ou ausente | Preencha `enable_password` nas credenciais |
| "Pattern not detected: 'HOSTNAME#'" | Timeout de paging | Verifique se `terminal length 0` é enviado após `enable()` |
| "---- More ----" truncando resposta | Paging não desabilitado | Verifique tratamento de paging no conector do vendor |
| "HP Comware requer Senha cmdline-mode" | Campo não preenchido | Edite o dispositivo e preencha `Senha cmdline-mode` |
| "commit failed" (Juniper) | Conflito de configuração | Rollback automático foi aplicado; verifique config existente |
| "Connection refused" | Porta SSH/REST fechada | Verifique se o serviço está ativo no dispositivo |
| "SSL: CERTIFICATE_VERIFY_FAILED" | Certificado autoassinado | Desative `verify_ssl` no cadastro do dispositivo |
| "404 Not Found" (pfSense) | Plugin pfsense-api não instalado | Instale o plugin no pfSense |
| "Invalid input detected" | Comando não suportado nessa versão | Revise o prompt do vendor ou verifique firmware |
