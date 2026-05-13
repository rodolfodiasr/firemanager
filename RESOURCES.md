# FireManager — Eternity SecOps
## Catálogo Completo de Recursos

> Versão: 0.1.0 — 27 fases implementadas  
> Stack: FastAPI · React 18 · PostgreSQL 15 + pgvector · Celery · Redis · Docker Compose

---

## Índice

1. [Visão Geral da Plataforma](#1-visão-geral-da-plataforma)
2. [Autenticação e Multi-tenant](#2-autenticação-e-multi-tenant)
3. [Gestão de Dispositivos](#3-gestão-de-dispositivos)
4. [Agente IA](#4-agente-ia)
5. [Operações em Dispositivos](#5-operações-em-dispositivos)
6. [Inspetor ao Vivo](#6-inspetor-ao-vivo)
7. [Bulk Jobs](#7-bulk-jobs)
8. [Golden Config (CLI)](#8-golden-config-cli)
9. [Golden Config Bundles REST](#9-golden-config-bundles-rest)
10. [Migração de Switches](#10-migração-de-switches)
11. [Migração de Regras de Firewall](#11-migração-de-regras-de-firewall)
12. [Conectividade de Rede](#12-conectividade-de-rede)
13. [Analista de Servidores N3](#13-analista-de-servidores-n3)
14. [Conectores de Banco de Dados](#14-conectores-de-banco-de-dados)
15. [Base de Conhecimento IA (RAG)](#15-base-de-conhecimento-ia-rag)
16. [Ciclo de Vida de Identidade — Offboarding](#16-ciclo-de-vida-de-identidade--offboarding)
17. [Ciclo de Vida de Identidade — Onboarding](#17-ciclo-de-vida-de-identidade--onboarding)
18. [Alertas e Integrações](#18-alertas-e-integrações)
19. [Dashboard Executivo](#19-dashboard-executivo)
20. [Plataforma Enterprise](#20-plataforma-enterprise)
21. [VM Migration Planner](#21-vm-migration-planner)
22. [Auditoria e Conformidade](#22-auditoria-e-conformidade)
23. [Integrações de Terceiros](#23-integrações-de-terceiros)
24. [Painel MSSP e Multi-tenant](#24-painel-mssp-e-multi-tenant)
25. [Vendors Suportados](#25-vendors-suportados)
26. [Arquitetura Técnica](#26-arquitetura-técnica)

---

## 1. Visão Geral da Plataforma

O **FireManager / Eternity SecOps** é uma plataforma MSSP (Managed Security Service Provider) para gestão centralizada de infraestrutura de segurança com inteligência artificial. Permite que provedores de serviços gerenciem firewalls, switches, servidores, identidade e VMs de múltiplos clientes (tenants) em uma única interface.

### Pilares principais

| Pilar | Descrição |
|-------|-----------|
| **Gestão Multivendor** | Suporte unificado a 18+ vendors via REST API e SSH/Netmiko |
| **IA Integrada** | Agente Claude (claude-sonnet-4-6) em todos os módulos analíticos |
| **Multi-tenant** | Isolamento completo por tenant com roles granulares |
| **Automação** | Celery workers para operações assíncronas e agendadas |
| **Observabilidade** | Prometheus + Grafana, audit log imutável, health checks automáticos |

---

## 2. Autenticação e Multi-tenant

### 2.1 Autenticação

- Login com e-mail e senha (bcrypt hash)
- JWT com expiração configurável
- MFA opcional (TOTP)
- Convite por e-mail com token de aceite (`/invite/:token`)
- Troca de senha autenticada

### 2.2 Modelo Multi-tenant

- Cada **Tenant** representa um cliente MSSP
- Três roles por tenant:
  - `admin` — gestão completa do tenant
  - `analyst` — leitura + operações aprovadas
  - `readonly` — somente leitura
- **Super Admin** (`is_super_admin=true`) — acesso cross-tenant sem tenant_id fixo no JWT
- Herança de variáveis: Tenant → Device (device sobrescreve)

### 2.3 Gestão de Organização

- CRUD de membros do tenant (convidar, remover, alterar role)
- Listagem de tenants ativos para super admin
- Painel MSSP cross-tenant com status global

### 2.4 API Keys (Fase 25)

- Geração de chaves `fm_` + token (SHA-256 hash armazenado)
- Prefix de 8 chars exibido na UI (chave completa mostrada apenas no momento da criação)
- Permissões granulares por key (ex: `devices:read`, `operations:write`)
- Rotação de chave sem downtime
- Data de expiração opcional
- Rastreamento de `last_used_at`

---

## 3. Gestão de Dispositivos

### 3.1 CRUD de Dispositivos

- Cadastro com: nome, vendor, host, porta, SSL, credenciais criptografadas (AES-256)
- Categoria: `firewall`, `switch`, `routing`, `server`, `hypervisor`
- Status automático: `online`, `offline`, `unknown`, `error`
- Agrupamento em **Device Groups** com tags e filtros
- Variáveis de template por device (sobrescrevem as do tenant)

### 3.2 Health Check Automático

- Celery Beat executa a cada 5 minutos
- Verifica conectividade REST ou SSH por vendor
- Atualiza `status`, `last_check_at`, `firmware_version`
- Dispara alerta `health_check_failed` se falhar

### 3.3 Grupos de Dispositivos

- Criação de grupos com nome e descrição
- Associação de múltiplos devices a um grupo
- Operações em lote direcionadas ao grupo inteiro

### 3.4 Category Roles e Module Roles

- **Category Roles**: permissões por categoria de device (firewall, switch, etc.)
- **Module Roles**: permissões por módulo funcional (golden config, connectivity, etc.)
- Controle fino de quem pode operar quais dispositivos

---

## 4. Agente IA

### 4.1 Conversação em Linguagem Natural

- Interface de chat com o agente Claude (claude-sonnet-4-6)
- Contexto injetado automaticamente: devices do tenant, regras, NATs, rotas
- Histórico de sessão persistido
- Injeção automática de documentos relevantes da Base de Conhecimento (RAG)

### 4.2 Capacidades do Agente

- Gerar planos de operações em linguagem natural
- Explicar regras de firewall em texto simples
- Sugerir otimizações de segurança
- Analisar logs e identificar anomalias
- Gerar comandos CLI para qualquer vendor suportado
- Criar documentação técnica de configurações

### 4.3 Modo Técnico (Direct Mode)

- Terminal direto para dispositivos via agente
- Execução de comandos SSH com resposta em tempo real
- Histórico de comandos por sessão

---

## 5. Operações em Dispositivos

### 5.1 Operações Disponíveis (por vendor)

| Operação | Fortinet | SonicWall | pfSense | OPNsense | MikroTik | SSH vendors |
|----------|----------|-----------|---------|----------|----------|-------------|
| Listar regras | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Criar regra | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Deletar regra | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Listar NATs | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Criar NAT | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Listar rotas | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Criar rota | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Snapshot config | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### 5.2 Fluxo de Aprovação

- Operações criadas ficam em status `pending_approval`
- Admin aprova ou rejeita com justificativa
- Operações aprovadas executam via Celery worker assíncrono
- Resultado registrado no audit log com diff

### 5.3 Audit Log

- Registro imutável de todas as operações
- Campos: tenant, device, usuário, tipo de operação, payload, resultado, timestamp
- Filtros: por device, por usuário, por status, por período
- Contador de pendentes exibido na sidebar

---

## 6. Inspetor ao Vivo

### 6.1 Snapshot em Tempo Real

- Coleta live de: regras de firewall, NATs, rotas estáticas, interfaces, VLANs
- Dados adicionais via SSH para SonicWall: content filter, app rules, security services
- Renderização em Markdown estruturado
- Exportação automática para BookStack (wiki)

### 6.2 Conteúdo por Vendor

| Seção | Fortinet | SonicWall | pfSense | OPNsense |
|-------|----------|-----------|---------|----------|
| Regras IPv4 | ✅ | ✅ | ✅ | ✅ |
| NAT/Port Forward | ✅ | ✅ | ✅ | ✅ |
| Rotas estáticas | ✅ | ✅ | ✅ | ✅ |
| Interfaces | ✅ | ✅ | ✅ | ✅ |
| Content Filter | ✅ | ✅ (SSH) | — | — |
| App Control | — | ✅ (SSH) | — | — |
| VPN Status | ✅ | ✅ | ✅ | ✅ |

---

## 7. Bulk Jobs

### 7.1 Operações em Lote

- Seleção de múltiplos devices ou grupos para aplicar a mesma operação
- Suporte a todas as operações disponíveis por vendor
- Execução paralela via Celery com controle de concorrência
- Resultado individual por device no relatório final

### 7.2 Bulk por Categoria

- Filtro de devices por categoria (todos os firewalls, todos os switches, etc.)
- Filtro por role de categoria (apenas devices onde o usuário tem permissão)
- Histórico de bulk jobs com status agregado

---

## 8. Golden Config (CLI)

### 8.1 Templates CLI

- Biblioteca de templates por vendor com variáveis tipadas `{VARIÁVEL}`
- Tipos de variável: string, number, ip_address, cidr, boolean, enum
- Validação de tipo antes da aplicação
- Diff entre configuração atual do device e template esperado (divergência)

### 8.2 Variáveis de Template

- Definição no nível do tenant (padrão)
- Sobrescrita no nível do device
- Herança automática: tenant → device
- CRUD completo de variáveis com histórico

### 8.3 Aplicação de Templates

- Preview do resultado antes de aplicar
- Aplicação via SSH com execução de comandos CLI
- Suporte a modo de configuração (`configure terminal` / `system-view`)
- Salvar configuração automático pós-aplicação

---

## 9. Golden Config Bundles REST

### 9.1 Conceito

Extensão da Fase 8 para firewalls modernos com API REST. Um **Bundle** agrupa múltiplas seções de configuração aplicadas em ordem, cobrindo implantação completa de filial com 1 clique.

### 9.2 Tipos de Seção

| Seção | Fortinet (REST) | Estratégia |
|-------|-----------------|------------|
| `base_config` | CLI SSH | cli_ssh |
| `objects` | `/cmdb/firewall/address` | rest_api |
| `access_rules` | `/cmdb/firewall/policy` | rest_api |
| `content_filter` | `/cmdb/webfilter/profile` | rest_api |
| `geo_ip` | `/cmdb/firewall/address` (geography) | rest_api |
| `vpn` | `/cmdb/vpn.ipsec/phase1-interface` | rest_api |
| `sd_wan` | `/cmdb/system/virtual-wan-link` | rest_api |

### 9.3 Estratégias de Aplicação

- `cli_ssh` — executa via SSH (integrado com Golden Config F8)
- `rest_api` — aplica via REST API do vendor
- `manual_only` — gera preview e aguarda aprovação humana

### 9.4 BundleRenderer

- Substitui `{VARIÁVEIS}` em templates JSON/CLI
- Herança: variáveis do bundle < variáveis do device < variáveis extras informadas no momento do apply
- Parse e validação de JSON antes da aplicação

### 9.5 Fluxo de Aplicação

1. Cria registro `BundleApply` (status: `applying`)
2. Celery worker itera seções em ordem de `apply_order`
3. Cada seção tem resultado individual registrado em JSONB
4. Status final: `applied` (todos ok) ou `failed` (alguma seção falhou)
5. Polling de status no frontend até conclusão

---

## 10. Migração de Switches

### 10.1 Parser de Configuração

- Import de configuração legada via upload de arquivo `.txt`/`.conf`
- Parsers implementados para: Intelbras, Juniper EX, Aruba
- Extração de: VLANs, interfaces, STP, LACP, rotas, ACLs

### 10.2 Geração de Configuração

- Renderização para o vendor de destino
- Validação de equivalência funcional
- Preview diff antes de aplicar
- Exportação para BookStack com documentação automática

### 10.3 Snapshot Automático

- Agendamento de snapshot periódico via Celery Beat
- Exportação automática para BookStack a cada execução
- Histórico de snapshots com comparação entre versões

---

## 11. Migração de Regras de Firewall

### 11.1 Parser de Regras

- Import de regras de: Fortinet, SonicWall, Sophos
- Normalização para IR (Intermediate Representation) comum
- Campos normalizados: nome, ação, src/dst zones, src/dst addresses, serviços, schedule, log

### 11.2 Renderer Multi-vendor

- Saída para qualquer vendor suportado a partir do IR
- Mapeamento de objetos de endereço, grupos de serviço, zonas
- Detecção de regras sem equivalente no destino (marcadas como `manual`)
- Relatório de incompatibilidades por regra

### 11.3 Migração Assistida por IA

- Nível de análise configurável (básico, completo)
- IA sugere equivalências e explica regras complexas
- Geração de relatório de migração em Markdown
- Exportação para BookStack

---

## 12. Conectividade de Rede

### 12.1 Coleta de Dados

- Tabela de rotas via SSH (todos os vendors suportados)
- Detecção de protocolo de roteamento: BGP, OSPF, EIGRP, SD-WAN, static
- Interfaces com IP, máscara, status (up/down)
- Peerings BGP com vizinhos e status de sessão

### 12.2 Detecção de Anomalias

- Rotas órfãs (next-hop inacessível)
- Rotas duplicadas com métricas conflitantes
- Interfaces admin-up/oper-down
- Peerings BGP down
- Cruzamento com dados Nmap (portas abertas x rotas)

### 12.3 Mapa de Topologia

- Grafo de conectividade entre devices do tenant
- Visualização de links e rotas entre dispositivos
- Destaque de anomalias no mapa

### 12.4 Análise IA

- Interpretação das anomalias detectadas
- Sugestões de correção
- Geração de relatório de conectividade em Markdown

---

## 13. Analista de Servidores N3

### 13.1 Módulo Read-Only

O módulo é puramente analítico — não executa comandos de modificação.

### 13.2 SSH Linux

Coleta de:
- Processos em execução (`ps aux`)
- Uso de disco por filesystem (`df -h`)
- Uso de memória (`free -m`)
- Logs de sistema (`journalctl`)
- Conexões de rede (`netstat -tlnp`)
- Uptime e carga

### 13.3 WinRM Windows

Coleta de:
- Serviços Windows (status, startType)
- Uso de disco por drive
- Processos em execução
- Event Log (Application, System)
- Usuários logados

### 13.4 Zabbix (v6.x e v7.x)

- Suporte a ambas as versões com detecção automática
- v6.x: token no body JSON-RPC
- v7.x: Bearer token no header
- Coleta de: hosts, problemas ativos, triggers, métricas

### 13.5 Wazuh

- Autenticação JWT (POST /security/user/authenticate)
- Coleta de: agentes, alertas recentes, regras disparadas, nível de criticidade
- Análise de alertas por severidade

### 13.6 Análise IA

- Interpretação dos dados coletados por Claude
- Identificação de problemas críticos
- Sugestões de remediação priorizadas
- Geração de relatório N3 em Markdown

### 13.7 Modo Técnico de Servidor

- Terminal direto para servidores via SSH
- Execução de comandos com histórico de sessão
- Suporte a múltiplas sessões simultâneas

---

## 14. Conectores de Banco de Dados

### 14.1 Bancos Suportados

| Banco | Driver | Porta padrão |
|-------|--------|--------------|
| PostgreSQL | asyncpg | 5432 |
| MySQL / MariaDB | aiomysql | 3306 |
| SQL Server | aioodbc / pymssql | 1433 |
| Oracle | cx_Oracle | 1521 |

### 14.2 Auditoria de Usuários

- Listagem de usuários do banco com últimas permissões
- Detecção de usuários com `SUPERUSER` / `DBA` / `SA`
- Usuários sem senha ou com senha padrão
- Logins recentes e falhas de autenticação

### 14.3 Auditoria de Privilégios

- Grants por usuário e por objeto
- Roles e group membership
- Detecção de privilégios excessivos (`ALL PRIVILEGES`)
- Diferença entre privilégios esperados e reais

### 14.4 Análise IA

- Interpretação dos achados de auditoria
- Classificação de riscos por criticidade
- Recomendações de hardening de banco
- Geração de relatório de auditoria em Markdown

---

## 15. Base de Conhecimento IA (RAG)

### 15.1 Upload de Documentos

- Formatos suportados: PDF, DOCX, Markdown (`.md`)
- Processamento assíncrono via Celery
- Extração de texto com bibliotecas especializadas por formato

### 15.2 Pipeline RAG

1. Extração de texto do documento
2. Chunking em fragmentos de ~1000 tokens
3. Geração de embeddings via Anthropic (ou local)
4. Armazenamento em PostgreSQL + pgvector
5. Busca por similaridade vetorial (cosine distance)

### 15.3 Injeção Automática no Agente

- A cada consulta ao agente IA, os top-K chunks mais relevantes são injetados no contexto
- Contexto identificado com fonte e página do documento
- Configurável por tenant (documentos ativos/inativos)

### 15.4 Gestão de Documentos

- Lista de documentos com status de indexação
- Ativação/desativação sem reprocessar
- Filtro por vendor ou módulo do sistema

---

## 16. Ciclo de Vida de Identidade — Offboarding

### 16.1 Provedores de Identidade

| Provedor | Protocolo | Sync |
|----------|-----------|------|
| Azure Active Directory | Microsoft Graph API | ✅ |
| Google Workspace | Directory API | ✅ |
| AD Local (LDAP) | ldap3 | ✅ |

### 16.2 Sincronização de Usuários

- Sync periódico de usuários dos provedores
- Campos: username, display_name, email, department, job_title, last_sign_in
- Detecção de usuários inativos/desabilitados

### 16.3 Detecção de Usuários Órfãos

- Cruzamento entre usuários do provedor e usuários nos sistemas gerenciados
- Usuário **órfão**: existe em sistemas mas não no provedor de identidade ativo
- Lista de órfãos com sistema de origem e última atividade
- Gatilho de alerta `orphan_detected` configurável

### 16.4 Offboarding Automatizado

**Sistemas cobertos pelo offboarding:**

| Sistema | Ação |
|---------|------|
| Azure AD | Desabilitar conta, revogar tokens |
| Google Workspace | Suspender conta, revogar sessões OAuth |
| AD Local (LDAP) | Desabilitar conta (userAccountControl) |
| SSH Linux | Bloquear login (`usermod -L`), encerrar sessões |
| WinRM Windows | Desabilitar conta local |
| PostgreSQL | Revogar todos os grants, desabilitar login |
| MySQL | Revogar grants, expirar senha |
| SQL Server | Desabilitar login |
| Oracle | Lock account |
| Guacamole | Desabilitar usuário via REST API |
| Tactical RMM | Desabilitar usuário |
| Unifi Network | Revogar admin |

### 16.5 Webhook de RH

- Endpoint receptor de eventos de RH (`POST /identity/webhook/hr`)
- Trigger automático de offboarding ao receber evento de desligamento
- Suporte a payload customizável por sistema de RH

### 16.6 Audit Trail de Offboarding

- `LifecycleAction` com status geral: `pending_discovery` → `pending_approval` → `running` → `completed/failed`
- `LifecycleTask` por sistema com resultado individual
- Histórico completo de todas as ações

---

## 17. Ciclo de Vida de Identidade — Onboarding

### 17.1 Perfis de Cargo

- Definição de perfis com nome e lista de grupos do AD
- Os grupos do AD cobrem automaticamente sistemas integrados (GLPI, Docs, SysPass) via membership
- Sistemas adicionais configurados diretamente no perfil

### 17.2 Conectores Externos

| Conector | Protocolo | Ação |
|----------|-----------|------|
| Guacamole | REST API (POST /api/tokens) | Criar usuário, definir conexões |
| Tactical RMM | REST API (X-API-KEY) | Criar usuário, definir role |
| Unifi Network | Cookie / UniFi OS token | Convidar admin |

### 17.3 Onboarding 1 Clique

1. Informar: username, display_name, email, perfil de cargo
2. Sistema cria `LifecycleAction` (action_type: onboard)
3. Tasks geradas: uma por sistema do perfil
4. Execução sequencial em background
5. Usuário adicionado aos grupos AD → acesso automático a GLPI, Docs, SysPass
6. Usuário criado em Guacamole, Tactical RMM, Unifi conforme perfil

### 17.4 Gestão de Perfis

- CRUD de perfis com editor de grupos AD (tag input)
- Associação de sistemas externos por perfil
- Config específica por sistema no perfil (ex: role no Tactical RMM, conexões no Guacamole)

---

## 18. Alertas e Integrações

### 18.1 Canais de Notificação

| Canal | Método | Campos de configuração |
|-------|--------|------------------------|
| Slack | Incoming Webhook | webhook_url |
| Microsoft Teams | Incoming Webhook (MessageCard) | webhook_url |
| E-mail SMTP | asyncio STARTTLS/SSL | host, port, user, password, from, to |
| Webhook genérico | HTTP POST/GET | url, method, headers JSONB |
| Jira Cloud | REST API v3 Basic Auth | base_url, email, token, project_key, issue_type |

### 18.2 Gatilhos de Alerta

| Gatilho | Quando dispara |
|---------|----------------|
| `offboard_completed` | Offboarding finalizado com sucesso |
| `onboard_completed` | Onboarding finalizado com sucesso |
| `task_failed` | Tarefa de lifecycle falhou |
| `health_check_failed` | Device ficou offline |
| `orphan_detected` | Usuário órfão identificado |

### 18.3 Regras de Alerta

- Criação de regras: gatilho + severidade (info/warning/critical) + canais destino
- Múltiplos canais por regra (checkbox)
- Ativação/desativação sem excluir
- Dispatch paralelo para todos os canais configurados

### 18.4 Histórico de Eventos

- Registro de cada disparo com: título, corpo, severidade, resultado por canal
- Status por canal: success / failed com detalhes do erro
- Filtros por severidade e gatilho

### 18.5 Teste de Canal

- Botão "Testar" envia mensagem de verificação para o canal
- Resultado imediato na UI (ok / erro com detalhe)

---

## 19. Dashboard Executivo

### 19.1 Score de Risco (0–100)

Calculado com pesos configuráveis sobre:
- Quantidade de usuários órfãos / total de usuários
- Alertas críticos ativos
- Offboardings pendentes
- Dispositivos offline

Classificação visual:
- 0–30: Verde (baixo risco)
- 31–60: Amarelo (risco moderado)
- 61–100: Vermelho (alto risco)

### 19.2 Métricas Consolidadas

| Métrica | Fonte |
|---------|-------|
| Total de usuários | identity_users |
| Usuários órfãos | detecção de orphans |
| Dispositivos online/offline | health checks |
| Ações de lifecycle (30d) | lifecycle_actions |
| Alertas críticos (7d) | alert_events |
| Offboardings pendentes | lifecycle_actions status |

### 19.3 Feeds de Atividade Recente

- Últimas ações de lifecycle com status
- Últimos alertas disparados
- Mudanças de status de dispositivos

### 19.4 Relatório PDF Executivo

- Gerado via WeasyPrint (HTML → PDF)
- Período configurável (7, 30, 90 dias)
- Conteúdo: score de risco, métricas, tabelas, feed de atividade
- Download direto pelo navegador

### 19.5 Auto-refresh

- Atualização automática a cada 60 segundos
- Indicador visual de última atualização

---

## 20. Plataforma Enterprise

### 20.1 White-label por Tenant

- Company Name customizado
- Cor primária (hex color picker)
- URL de logo customizada
- URL de favicon customizada
- Configuração independente por tenant

### 20.2 API Keys

- Geração de chaves de API para integração externa
- Prefixo `fm_` + token de 29 chars (total ~40 chars)
- SHA-256 do token armazenado (nunca o token em plain text)
- Permissões por key (lista de escopos)
- Expiração opcional
- Rotação sem downtime
- Rastreamento de último uso

### 20.3 Novos Vendors Enterprise

| Vendor | Tipo | Protocolo | Autenticação |
|--------|------|-----------|--------------|
| Cisco ASA | Firewall | SSH/Netmiko | username/password + enable |
| Palo Alto PAN-OS | Firewall | REST API v10.2 | `X-PAN-KEY` header |
| Check Point R80+ | Firewall | REST API | Session (POST /web_api/login → X-chkp-sid) |

---

## 21. VM Migration Planner

### 21.1 Filosofia

Módulo 100% **read-only** — coleta, inventária e planeja. Não executa nenhuma migração automaticamente.

### 21.2 Hypervisors Suportados

| Hypervisor | API | Auth |
|------------|-----|------|
| VMware vCenter | vSphere REST API v7+ | POST /api/session (Basic auth) |
| Proxmox VE | Proxmox API | POST /api2/json/access/ticket |
| Hyper-V | WinRM | (planejado) |

### 21.3 Inventário de VMs

Campos coletados por VM:
- Nome, ID interno do hypervisor
- Estado de energia (running, stopped, suspended)
- OS (tipo/versão quando disponível)
- vCPUs, RAM (MB), Disco total (GB)
- Endereços IP (quando VMware Tools disponível)
- Tags e metadados extras

### 21.4 Sincronização

- Sync manual por botão na UI
- Apaga inventário antigo e reinsere dados frescos
- Atualiza `last_sync_at` e `last_vm_count` no hypervisor
- Suporte a até 100 VMs por sync (VMware) / ilimitado (Proxmox)

### 21.5 Runbooks de Migração com IA

Geração de runbook completo em Markdown via Claude (claude-sonnet-4-6):
- Checklist pré-migração
- Ordem sugerida de migração (por risco e dependência)
- Passos detalhados por grupo de VMs
- Mudanças de rede necessárias
- Procedimento de rollback
- Testes de validação pós-migração
- Janelas de manutenção estimadas

Geração assíncrona em background — UI mostra spinner e auto-refresh até ficar `ready`.

---

## 22. Auditoria e Conformidade

### 22.1 Audit Log

- Registro imutável de todas as operações
- Filtros: device, usuário, tipo, status, período
- Detalhes: payload enviado, resposta recebida, diff de config
- Exportação CSV

### 22.2 Conformidade

- Scan automático de conformidade por device
- Políticas configuráveis por categoria de device
- Relatório de conformidade com itens aprovados/reprovados
- Score de conformidade por device e por tenant

### 22.3 Governança

- Trust Score por device (composto de health, compliance, última operação)
- Ranking de devices por confiabilidade
- Alertas de regressão de score

### 22.4 Remediações

- Planos de remediação gerados por IA a partir de achados de conformidade
- Priorização por impacto e facilidade de correção
- Rastreamento de status (pendente, em andamento, concluído)
- Rollback de remediação com captura de snapshot

---

## 23. Integrações de Terceiros

### 23.1 BookStack (Wiki)

- Exportação automática de snapshots de dispositivos
- Criação/atualização de páginas por device
- Indexação de conteúdo para busca
- Sincronização periódica via Celery

### 23.2 GLPI (Service Desk)

- Listagem de tickets vinculados ao tenant
- Análise de tickets por IA (categorização, prioridade, solução sugerida)
- Correlação de tickets com devices afetados
- Sincronização periódica via Celery (a cada 5 min)

### 23.3 Nmap

- Scan de rede para descoberta de hosts e portas
- Cruzamento com tabela de rotas (conectividade)
- Detecção de hosts não inventariados

### 23.4 Shodan

- Consulta de exposição pública de IPs dos devices
- Detecção de serviços expostos na internet
- Alertas de portas abertas inesperadas

### 23.5 Wazuh

- Coleta de alertas de segurança de endpoints
- Integração com módulo de servidores (Analista N3)
- Correlação de alertas com devices gerenciados

### 23.6 OpenVAS

- Scan de vulnerabilidades de rede
- Importação de resultados para relatório de conformidade

### 23.7 Prometheus + Grafana

- Métricas da API expostas em `/metrics`
- Dashboard Grafana pré-configurado para monitoramento da plataforma
- Métricas: latência de requests, uso de CPU/memória, jobs Celery

---

## 24. Painel MSSP e Multi-tenant

### 24.1 Dashboard MSSP (Super Admin)

- Visão cross-tenant de todos os clientes
- Status de saúde por tenant (devices online/offline)
- Últimas operações cross-tenant
- Alertas críticos de qualquer tenant

### 24.2 Gestão de Tenants

- CRUD de tenants com configurações individuais
- Limites por tenant (planejado: billing)
- Transferência de devices entre tenants
- Isolamento garantido: cada query filtra por tenant_id

---

## 25. Vendors Suportados

### Firewalls

| Vendor | Versões | Protocolo | Desde |
|--------|---------|-----------|-------|
| Fortinet FortiGate | FortiOS 7.x | REST API | F1 |
| SonicWall | SonicOS 6.x e 7.x | REST API + SSH | F1 |
| pfSense | 2.6+ | REST API | F6 |
| OPNsense | 23.x+ | REST API | F6 |
| MikroTik | RouterOS 6/7 | REST API | F6 |
| Endian Firewall | 3.x | SSH | F6 |
| Sophos XG/XGS | SFOS 18+ | REST API | F16 |
| Cisco ASA | 9.x+ | SSH/Netmiko | F25 |
| Palo Alto PAN-OS | 10.x+ | REST API v10.2 | F25 |
| Check Point | R80+ | REST API | F25 |

### Switches e Roteadores

| Vendor | Modelo/OS | Protocolo | Desde |
|--------|-----------|-----------|-------|
| Cisco IOS | IOS 15+, IOS-XE | SSH/Netmiko | F9 |
| Cisco NX-OS | NX-OS 7+ | SSH/Netmiko | F9 |
| Juniper | EX Series, JunOS | SSH/Netmiko | F15 |
| Aruba | ArubaOS-Switch | SSH/Netmiko | F15 |
| Dell OS10 | SmartFabric OS10 | SSH/Netmiko | F9 |
| Dell N-Series | DNOS6 (N1524P, N2000, N3000) | SSH/Netmiko | F11 |
| HP Comware | V1910, V3600, A-Series | SSH/Netmiko | F12 |
| Ubiquiti UniFi | EdgeOS | SSH/Netmiko | F9 |
| EdgeSwitch | EdgeMax 1.x/2.x | SSH/Netmiko | F9 |

### Hypervisors

| Vendor | API | Desde |
|--------|-----|-------|
| VMware vCenter | vSphere REST v7+ | F27 |
| Proxmox VE | Proxmox API | F27 |

---

## 26. Arquitetura Técnica

### 26.1 Stack

| Componente | Tecnologia | Versão |
|------------|-----------|--------|
| Backend | FastAPI + Python | 3.11 |
| ORM | SQLAlchemy async + asyncpg | 2.x |
| Migrations | Alembic | — |
| Frontend | React + TypeScript + Vite | 18 + 5 |
| CSS | Tailwind CSS | 3.x |
| Estado | @tanstack/react-query + zustand | — |
| Workers | Celery + Redis | 5.x + 7.2 |
| Banco | PostgreSQL 15 + pgvector | 15 |
| Proxy | nginx (reverse proxy + static) | alpine |
| IA | Anthropic Claude (claude-sonnet-4-6) | — |
| SSH | Netmiko | 4.x |
| PDF | WeasyPrint | — |
| Monitoramento | Prometheus + Grafana | — |
| Infra | Docker Compose | — |

### 26.2 Segurança

- Credenciais de devices: AES-256 (encrypt_credentials / decrypt_credentials)
- Senhas de usuários: bcrypt
- API Keys: SHA-256 do token (nunca armazenado em plain text)
- Configs de canais de alerta: AES-256 (encrypted_config)
- Credenciais de identity providers: AES-256
- JWT com expiração configurável
- CORS configurável por ambiente

### 26.3 Migrações Alembic

| Range | Descrição |
|-------|-----------|
| 0001–0013 | Schema base: devices, tenants, users, operations, audit, variables, servers |
| 0014–0020 | Roles, compliance, governance, GLPI, knowledge |
| 0021–0027 | Config migrations, golden templates, connectivity, bookstack |
| 0028–0033 | Knowledge documents, pgvector, database connectors |
| 0034 | Database connectors |
| 0035 | Identity providers + lifecycle |
| 0036 | Onboarding (external connectors, profiles) |
| 0037 | Alertas (channels, rules, events) |
| 0038 | Enterprise (tenant_branding, api_keys) |
| 0039 | Golden Bundles (golden_bundles, bundle_sections, bundle_applies) |
| 0040 | VM Migration (vm_hypervisors, vm_inventory, migration_runbooks) |

### 26.4 Celery Workers e Tasks

| Task | Schedule | Descrição |
|------|----------|-----------|
| `health_check.run_health_checks` | A cada 5 min | Verifica status de todos os devices |
| `bookstack_snapshot.run_bookstack_snapshots` | A cada hora | Snapshot automático para BookStack |
| `bookstack_index.run_bookstack_indexing` | A cada 6 horas | Re-indexa documentos BookStack |
| `compliance_scan.run_compliance_scan` | Diário 02:00 UTC | Scan de conformidade em todos os devices |
| `glpi_sync.run_glpi_sync` | A cada 5 min | Sincroniza tickets do GLPI |
| `workers.apply_golden_bundle` | On-demand | Aplica Golden Bundle REST em device |
| `execute_operation` | On-demand | Executa operação aprovada em device |
| `generate_documents` | On-demand | Gera documentação de snapshot |
| `migration_worker` | On-demand | Processa migração de regras de firewall |

### 26.5 Tabelas do Banco de Dados

| Tabela | Módulo |
|--------|--------|
| tenants, users, tenant_members | Auth/Multi-tenant |
| devices, device_groups, device_group_members | Dispositivos |
| template_variables, device_variables | Variáveis |
| operations, audit_logs | Operações |
| bulk_jobs, bulk_job_items | Bulk |
| golden_templates, template_variables | Golden Config CLI |
| golden_bundles, bundle_sections, bundle_applies | Golden Bundles REST |
| config_migrations, firewall_migrations | Migrações |
| connectivity_analyses, connectivity_pairs | Conectividade |
| servers, server_sessions | Servidores |
| database_connectors | Banco de Dados |
| knowledge_documents, knowledge_chunks | RAG |
| identity_providers, identity_users | Identidade |
| lifecycle_actions, lifecycle_tasks | Lifecycle |
| external_connectors, onboarding_profiles, onboarding_profile_systems | Onboarding |
| alert_channels, alert_rules, alert_events | Alertas |
| tenant_branding, api_keys | Enterprise |
| vm_hypervisors, vm_inventory, migration_runbooks | VM Migration |
| compliance_reports, compliance_items | Conformidade |
| remediation_plans, remediation_items | Remediações |
| glpi_integrations, glpi_analyses | GLPI |

---

*Documento gerado em 2026-05-08 — FireManager v0.1.0*
