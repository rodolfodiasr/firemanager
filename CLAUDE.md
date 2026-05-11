# FireManager — Guia de Contexto para Claude Code

## O que é este projeto

FireManager é uma plataforma MSSP (Managed Security Service Provider) para gestão centralizada de firewalls com IA. Backend FastAPI/Python, frontend React/TypeScript, PostgreSQL + pgvector, Celery/Redis, Docker Compose.

**Stack:**
- Backend: FastAPI + SQLAlchemy async + asyncpg + Alembic
- Frontend: React 18 + TypeScript + Vite
- IA: Anthropic Claude (claude-sonnet-4-6) via SDK Python
- Workers: Celery + Redis
- DB: PostgreSQL 15 + pgvector
- Infra: Docker Compose em `infra/docker-compose.yml`

---

## Comandos essenciais

```bash
# O docker-compose.yml está em infra/ — SEMPRE usar -f
cd /home/admeternity/firemanager
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml build api
docker compose -f infra/docker-compose.yml logs -f api
docker compose -f infra/docker-compose.yml ps

# Serviços: api, celery_worker, celery_beat, postgres, redis, frontend, nginx, prometheus, grafana
# NUNCA usar: docker compose restart backend (serviço se chama "api", não "backend")

# Após qualquer restart de container de backend, reiniciar nginx:
docker compose -f infra/docker-compose.yml restart nginx
# Motivo: nginx faz cache de DNS — sem reiniciar, aponta para IP antigo e retorna 502

# Executar migrations no container
docker compose -f infra/docker-compose.yml exec api alembic upgrade head

# Executar SQL no PostgreSQL (flag -T obrigatória para pipar)
docker compose -f infra/docker-compose.yml exec -T postgres psql -U fm_user -d firemanager
# Usuário é fm_user, NÃO postgres
```

---

## Workflow de desenvolvimento (Windows → Linux VM)

**Problema crítico:** Claude Code roda no Windows (`C:\Users\rodolfo.dias\firemanager\`). O Docker roda em VM Linux (`/home/admeternity/firemanager/`). São filesystems SEPARADOS — edições no Windows NÃO chegam automaticamente ao Linux.

**Fluxo correto:**
1. Editar arquivos no Windows (Claude Code edita aqui)
2. Sincronizar para VM Linux (git push + pull, rsync, ou copiar manualmente)
3. O volume mount `../backend:/app` + hot-reload do uvicorn detecta mudanças na VM

**Verificar se mudanças chegaram ao Linux:**
```bash
grep -n "texto_do_codigo_novo" /home/admeternity/firemanager/backend/app/services/arquivo.py
```

**Para aplicar patches urgentes direto na VM sem sincronizar:**
- Usar Python one-liners com `python3 -c '...'` (sem heredoc — heredoc é corrompido pelo terminal SSH)
- Ou editar com `nano` diretamente na VM

---

## Anti-patterns críticos

### Docker
- ❌ `docker compose up` sem `-f infra/docker-compose.yml` → "no configuration file provided"
- ❌ `docker compose restart backend` → serviço se chama `api`
- ❌ Restart de `api` sem reiniciar `nginx` → 502 silencioso por DNS cache
- ❌ `docker compose exec postgres psql -U postgres` → usuário é `fm_user`
- ❌ Pipar SQL sem flag `-T`: `exec -T postgres psql ...`

### Python/Backend
- ❌ Esquecer `await db.refresh(objeto)` após `await db.flush()` → `MissingGreenlet` em campos `onupdate=func.now()`
- ❌ `creds.get("vdom", "root")` quando o valor pode ser `null` no JSON → usar `creds.get("vdom") or "root"`
- ❌ `payload.update(spec.extra)` direto → `spec.extra` pode ter campos inválidos para o vendor

### Segurança
- ❌ Gerar hash bcrypt em variável de shell e interpolar em SQL → `$` do hash é interpretado pelo bash
- ✅ Correto: gerar SQL completo via Python dentro do container, salvar em `/tmp/update.sql`, executar via pipe

### IA / Claude API
- ❌ Modelo `claude-sonnet-4-20250514` não existe → usar `claude-sonnet-4-6`
- Verificar API key: `docker exec api env | grep ANTHROPIC`

---

## Modelo de dados — Multi-tenant

- `is_super_admin: bool` no User → acesso cross-tenant (suporte MSSP)
- Super admin **não tem** `tenant_id` no JWT — queries devem ter branch explícita para super admin
- `TenantRole`: `admin`, `analyst`, `readonly`
- Herança de variáveis: Tenant → Device (device sobrescreve tenant)

---

## Roadmap Completo

### Fases Implementadas

| Fase | Descrição | Entregáveis principais | Status |
|---|---|---|---|
| 1 | Scaffold MVP | Devices, operações CRUD, agente IA (Claude), auth JWT | ✅ |
| 2 | Multi-tenant / MSSP | Tenants, roles (admin/analyst/readonly), super admin cross-tenant | ✅ |
| 3 | Integrações externas | Nmap, Shodan, Wazuh, OpenVAS | ✅ |
| 4 | Dashboard Super Admin | Painel cross-tenant, health status global | ✅ |
| 5 | Convites e self-service | Convite por email, accept invite, gestão de usuários por tenant | ✅ |
| 6 | Novos vendors firewall | pfSense, OPNsense, MikroTik, Endian | ✅ |
| 7 | Bulk Jobs | Operações em lote em múltiplos devices | ✅ |
| 8 | Inspetor ao vivo | Snapshot de device em tempo real (regras, NAT, rotas, interfaces) | ✅ |
| 9 | Bulk jobs por categoria | Roles de categoria, filtro de devices por grupo/função | ✅ |
| 10 | Grupos de dispositivos | Device groups, operações em grupo | ✅ |
| 11 | Dell N-Series (DNOS6) | Suporte CLI Dell N-Series via Netmiko | ✅ |
| 12 | HP V1910 (Comware) | Suporte CLI HP Comware via Netmiko | ✅ |
| 13 | Variáveis de template | Herança tenant → device, substituição em templates CLI | ✅ |
| 14 | Analista de Servidores | SSH Linux, WinRM Windows, Zabbix v6/v7, Wazuh — módulo analítico N3 | ✅ |
| 15 | Migração de Switches | Juniper EX, Aruba, Intelbras; BookStack; Zabbix dual-version; snapshot scheduling | ✅ |
| 16 | Migração de Regras | Parser + renderer Fortinet/SonicWall/Sophos; IR normalizado; Celery worker | ✅ |
| 17 | Golden Config | Templates com variáveis tipadas, biblioteca por vendor, divergência device×template | ✅ |
| 18 | Conectividade de Rede | Routing tables SSH, BGP/OSPF/SD-WAN, anomalias, cruzamento Nmap, mapa topologia, IA | ✅ |
| 19 | Base de Conhecimento IA | RAG: upload PDF/DOCX/MD, pgvector, embeddings, injeção automática no agente | ✅ |
| 20 | Conectores de Banco | PostgreSQL, MySQL/MariaDB, SQL Server, Oracle; auditoria usuários/privilégios; IA | ✅ |
| 21 | Ciclo de Vida — Offboarding | Azure AD, Google Workspace, AD Local (LDAP); offboard SSH/WinRM/DB; órfãs; webhook RH | ✅ |
| 22 | Ciclo de Vida — Onboarding | Perfis de cargo; grupos AD (GLPI/Docs/SysPass automáticos); Guacamole; Tactical RMM; Unifi | ✅ |
| 23 | Alertas & Integrações | Slack, Teams, Email SMTP, Webhook, Jira; regras por gatilho e severidade; histórico | ✅ |
| 24 | Dashboard Executivo | Score de risco 0–100, métricas agregadas, relatório PDF executivo (WeasyPrint) | ✅ |
| 25 | Plataforma Enterprise | API Keys, White-label branding, Cisco ASA + Palo Alto + Check Point connectors; migração 0038 | ✅ |
| 26 | Golden Config Bundles REST | GoldenBundle + BundleSection + BundleApply; BundleRenderer; FortinetRestApply; Celery worker; migração 0039 | ✅ |
| 27 | VM Migration Planner | VMware vCenter + Proxmox read-only; inventory sync; runbook IA (Claude); migração 0040 | ✅ |

---

### Próximas Fases

---

### Fase 28 — Segurança Avançada e Resiliência
*Hardening de autenticação, proteção de infraestrutura, tolerância a falhas e segurança do agente IA*

**Origem:** Mesa Redonda Segurança da Informação (20 profissionais) — Rafael (CISO), Ana (Red Team/AI), Eduardo (AI/ML), Thiago (Network), Vanessa (AppSec), Marcos (IR), Paulo (OT), Fernanda (Zero Trust), Sandra (Architecture), André (Bug Bounty)

| Funcionalidade | Detalhe | Prioridade |
|---|---|---|
| **Preview CLI exato antes de executar** | Exibir o bloco de comandos literal que será enviado ao device, linha por linha, antes da aprovação humana — técnico aprova o comando, não a intenção | **Crítica** |
| **Snapshot obrigatório antes de toda escrita** | Toda operação de escrita (não só bundles) dispara snapshot automático pré-execução; snapshot pós-execução registrado; rollback disponível em 1 clique | **Crítica** |
| **Denylist de comandos catastróficos por vendor** | Lista curta (~5–10 por vendor) de comandos irreversíveis bloqueados independente de aprovação: `factoryreset`, `formatlogdisk`, `delete all`, `wipe config`; allowlist seria restritiva demais — denylist cobre o único cenário onde preview + snapshot não bastam | **Crítica** |
| **AI output schema validation** | Validar output estruturado do Claude contra schema esperado (source, destination, action, etc.) antes de executar; rejeitar output fora do schema | Alta |
| **Prompt injection detection** | Sanitizar toda entrada enviada ao Claude — input do usuário, dados dos devices (nomes de políticas, comentários), documentos RAG; detectar padrões de injection | Alta |
| JWT short-lived + refresh httpOnly | Tokens de acesso TTL 15 min; refresh token em cookie httpOnly/Secure/SameSite=Strict; logout invalida token no servidor | Alta |
| SSRF protection (scheme + IP allowlist) | Bloquear IPs RFC1918, 169.254.169.254, localhost; allowlist de scheme (só `http://`/`https://`); validação de DNS antes de conectar | Alta |
| BOLA/IDOR checks | Verificação explícita de tenant em cada object-level access; validar `device_id` pertence ao tenant em todo endpoint de update/delete | Alta |
| **Hash-chained audit log** | Cada entrada de audit contém hash SHA-256 da entrada anterior; adulteração detectável; ancoragem periódica via RFC 3161 timestamping | Alta |
| Circuit breaker nos connectors | Padrão circuit breaker (tenacity) — vendor lento não bloqueia workers Celery | Alta |
| CI/CD com SAST + secret scanning | GitHub Actions: Bandit, pip-audit, Trivy, semgrep, truffleHog/detect-secrets; bloquear merge em findings críticos ou credentials hardcoded | Alta |
| **Modo read-only forçado por device** | Flag por device que impede toda operação de escrita via agente — para clientes OT/ICS, utilities, saúde que nunca autorizam escrita automatizada | Alta |
| **Token de convite único + expiração 24h** | Token de convite de uso único; expiração em 24h; invalidação automática após primeiro uso | Alta |
| Supply chain security | Pinagem de dependências com hash; Dependabot/Renovate; versionamento de parsers por firmware de vendor | Média |
| Rate limiting por API key | Limites configuráveis por tenant e por rota; headers `X-RateLimit-*` | Média |
| **Canal público de reporte de vuln** | E-mail `security@` com PGP key publicada; SLA de resposta: crítico 24h, alto 7d, médio 30d | Média |

---

### Fase 29 — Observabilidade, IA FinOps, Qualidade e Resiliência de IA
*Rastreabilidade de IA, controle de custos, qualidade de código, dry-run e resiliência de modelo*

**Origem:** Mesa Redonda Segurança — Dr. Eduardo (AI/ML), Felipe (Responsible AI), Diego (Threat Intel), Carlos (SOC)

| Funcionalidade | Detalhe | Prioridade |
|---|---|---|
| AI observability (logs + anti-injection) | Logging completo de prompts/respostas; validação de entrada; detecção de prompt injection; rastreabilidade prompt→comando→resposta do device | Alta |
| **AI dry-run / modo simulação** | Antes de executar, rodar o comando em modo simulado (onde vendor suporta) ou exibir diff previsto; resultado comparado com estado atual do device | Alta |
| **Confidence threshold + escalação** | Se Claude expressa incerteza ou o output tem score baixo de confiança, escalar para revisão humana em vez de prosseguir; nunca fingir certeza | Alta |
| Token tracking por tenant | Contador de tokens (input/output) por tenant por mês; alerta ao atingir quota; dashboard de consumo | Alta |
| Quotas e billing IA | Limite configurável de tokens/sessões por plano; throttle gracioso quando exceder | Alta |
| **AI fallback (Anthropic → OpenAI → Ollama)** | Fallback automático em cadeia se Anthropic indisponível; testado em failover drill semestral | Alta |
| **Rotação da chave Fernet** | Rotação anual da chave de criptografia de credenciais; re-encrypt automático de todos os valores cifrados; histórico de chaves para decrypt de dados antigos | Alta |
| Chunking semântico para RAG | Substituir chunking fixo por chunking por seção; reranking BM25+embeddings; sanitização de documentos no upload | Média |
| Análise de qualidade de regras | Detectar regras duplicadas, sobrepostas, sombra, `any/any allow`, hit count zero | Alta |
| Diagnóstico de qualidade de link | Histórico ICMP/RTT; alertas de latência anômala; exportar Grafana | Média |

---

### Fase 30 — Compliance Enterprise e Continuidade de Negócio
*Pacotes regulatórios, documentação legal, SLA formal e disaster recovery*

**Origem:** Mesa Redonda Rounds 1, 2 e 3 — Flávia (Compliance), Patrícia (Privacidade), Augusto (LGPD), Eduardo (BC/DR), Mônica (SLA)

| Funcionalidade | Detalhe | Prioridade |
|---|---|---|
| Compliance packs por vertical | Checklist CIS, PCI-DSS, BACEN Res. 4.658, LGPD Art. 46 — relatórios de conformidade por vertical | Alta |
| DPA / LGPD template | Template de Contrato de Tratamento de Dados (DPA) gerado automaticamente; cláusula de transferência internacional (Anthropic USA) | Alta |
| RTO/RPO documentados | Plano BCP com objetivos de recuperação; backup automático com teste de restore periódico | Alta |
| SLA formal com créditos automáticos | SLA por plano (ex: 99,9% uptime); cálculo e crédito automático via billing em caso de violação | Média |
| Relatório executivo de compliance | PDF executivo com score por framework (CIS/PCI/LGPD); evolução mensal; assinatura digital | Média |
| Data residency | Flag por tenant para garantir dados em região específica (BR); metadados de localização em audit log | Baixa |

---

### Fase 31 — Expansão de Plataforma e White-label Completo
*Edge agent, suporte CGNAT, revendas completas e estratégia open core*

**Origem:** Mesa Redonda Rounds 2 e 3 — Leonardo (Infra), Sérgio (Redes/ISP), Flávia (Revenda), Juliana (Produto)

| Funcionalidade | Detalhe | Prioridade |
|---|---|---|
| Edge agent on-premise | Agente leve (Python/Go) que abre WebSocket/gRPC de saída para o SaaS; sem porta inbound | Alta |
| Suporte a CGNAT | Edge agent resolve o problema de endereços NAT de ISPs brasileiros; reconecta automaticamente | Alta |
| White-label completo | Domínio customizado (CNAME), email transacional (logo+cores), relatório PDF com marca do parceiro | Alta |
| Open core — connectors OSS | Repositório público com connectors + parsers de vendors; licença Apache 2.0; contribuições externas | Média |
| Programa de certificação parceiros | Trilha de certificação técnica para revendedores; portal de parceiros com leads e comissões | Média |
| SSO / OIDC | SAML 2.0 / OIDC — Azure AD, Okta, Google Workspace; mapeamento de grupos para TenantRole | Alta |
| RBAC granular | Permissões por cliente/device/operação além dos 3 roles atuais; scopes por API key | Média |
| Marketplace de plugins | Plugins de vendor contribuídos por parceiros; review/publicação pelo time FireManager | Baixa |

---

### Fase 32 — Produto, UX e Documentação
*Experiência do usuário, acessibilidade, documentação por persona e internacionalização*

**Origem:** Mesa Redonda Rounds 2 e 3 — André (Produto), Beatriz (UX/Acessibilidade), Juliana (GTM), Cristina (CS)

| Funcionalidade | Detalhe | Prioridade |
|---|---|---|
| Documentação pública por persona | Docs separados: Admin MSSP, Analista N2, Cliente final; Swagger interativo por módulo | Alta |
| Billing e planos | Planos (Starter/Pro/Enterprise); limites de devices; cobrança automatizada (Stripe); fatura automática | Alta |
| Multi-idioma (i18n) | pt-BR ✅, en-US, es-LA; detecção automática do idioma do browser | Média |
| Acessibilidade (WCAG 2.1 AA) | Contraste para daltônicos (palete testada), navegação por teclado, labels ARIA, leitor de tela | Média |
| Onboarding guiado | Wizard de primeiros passos: add device → primeiro snapshot → primeira regra | Média |
| Feedback in-app | Widget de feedback contextual por página; integrado ao Linear/Jira interno | Baixa |

---

### Fase 33 — IA Safety & Governança
*Controles formais de segurança do agente IA, aprovação avançada e framework de governança*

**Origem:** Mesa Redonda Segurança da Informação — Felipe (Responsible AI), Larissa (LGPD), Marcos (IR), Carlos (SOC), Paulo (OT), Mônica (SecOps), Rafael (CISO), Ana (Red Team)

| Funcionalidade | Detalhe | Prioridade |
|---|---|---|
| **Aprovação dupla para devices críticos** | Flag "device crítico" por tenant; operações de escrita exigem 2 aprovadores distintos (four-eyes principle); fila de aprovação com timeout | Alta |
| **Janela de manutenção por device** | Operações de escrita via agente só executam dentro de janelas configuradas; fora da janela vão para fila pendente com notificação | Alta |
| **Termos de Uso e política de IA** | Documento publicado: o que o agente pode e não pode fazer; limitação de responsabilidade; uso aceitável; assinatura eletrônica pelo admin do tenant | Alta |
| **Security Incident Response Plan (SIRP) para IA** | Playbook documentado: o que fazer se agente executar operação não autorizada; quem notificar; RTO de comunicação ao cliente ≤ 2h | Alta |
| **Red team trimestral do agente** | Exercício formal de tentativa de prompt injection, manipulação de contexto RAG, jailbreak; resultado documentado e corrigido antes do próximo trimestre | Alta |
| **Four-eyes para operações de gestão** | Alterações em configuração de tenant, promoção de admin, alteração de allowlist de comandos — exigem segundo aprovador | Alta |
| **Validação de DPA com Anthropic** | Verificar adequação do contrato com Anthropic à LGPD (ANPD Res. 19/2024); cláusula de transferência internacional; notificar clientes | Alta |
| **Direito ao esquecimento (data deletion)** | Endpoint de exclusão completa de tenant: dados, snapshots, logs, credenciais, embeddings, documentos RAG; confirmação auditada | Alta |
| **Ancoragem de audit log em RFC 3161** | Timestamping criptográfico de blocos do audit log via autoridade confiável; prova irrefutável em juízo | Média |
| **Dashboard de postura interna** | Painel interno (só Super Admin): tentativas de login com falha, operações de escrita por tenant, anomalias de volume, circuit breakers abertos | Média |

---

### Fase 34 — Infraestrutura de Segurança Avançada
*mTLS interno, KMS/HSM, microsegmentação, OPA e observabilidade de segurança*

**Origem:** Mesa Redonda Segurança — Sandra (Architecture), Roberto (Crypto), Juliana (Cloud), Fernanda (Zero Trust), Mônica (SecOps), Diego (Threat Intel)

| Funcionalidade | Detalhe | Prioridade |
|---|---|---|
| **mTLS entre serviços internos** | Comunicação api↔celery↔redis com mTLS; redis com autenticação obrigatória; sem tráfego interno em plaintext | Alta |
| **KMS / HashiCorp Vault** | Chave Fernet e secrets de infraestrutura no Vault ou AWS KMS; nunca em `.env`; rotação automática; auditoria de acesso às chaves | Alta |
| **Microsegmentação Docker** | Redes Docker separadas por serviço; api não acessa postgres diretamente (só via ORM); celery não acessa redis além do necessário | Alta |
| **Open Policy Agent (OPA)** | Ponto central de decisão de autorização; políticas declarativas em Rego; facilita auditoria e consistência cross-serviço | Média |
| **Container security hardening** | AppArmor/seccomp profiles nos containers; usuário não-root nas imagens; read-only filesystem onde possível; scan Trivy em CI | Alta |
| **Gestão de vulnerabilidades formal** | Scan semanal automatizado (Trivy + Bandit + pip-audit); SLA de correção: crítico 24h, alto 7d, médio 30d; relatório mensal ao CISO | Alta |
| **Pentest externo anual** | Relatório de pentest por empresa credenciada; findings públicos (responsável disclosure após 90d); bug bounty privado HackerOne | Média |
| **Supply chain: parser versionado por firmware** | Parsers de CLI versionados por firmware do vendor; alerta quando output de device muda estruturalmente; sanitização de dados do device | Média |

---

### Fase 35 — SOAR & Threat Intelligence
*Resposta automatizada a incidentes, inteligência de ameaças e detecção avançada*

**Origem:** Mesa Redonda Segurança — Mônica (SecOps/SOAR), Diego (Threat Intel), Carlos (SOC), Leonardo (Pentester)

| Funcionalidade | Detalhe | Prioridade |
|---|---|---|
| **SOAR leve embutido** | Playbooks de resposta automática: score cai 20pts em 5min → agente entra em read-only, notifica CISO do cliente, abre ticket de incidente | Alta |
| **Threat Intelligence feed** | Integração com feeds de IoCs (IPs maliciosos, hashes, domínios); cruzamento com IPs nos firewalls gerenciados; alertas de match | Alta |
| NDR (Network Detection & Response) | Análise de padrões de tráfego anômalo nos devices gerenciados; baseline comportamental; alerta de desvio | Média |
| **Isolamento automático de device** | Em incidente confirmado, colocar device em modo read-only automático + notificar; reativação manual com aprovação dupla | Alta |
| Correlação de alertas cross-tenant | Super Admin vê padrões de ataque que afetam múltiplos tenants simultaneamente (campanha coordenada) | Média |

---

### Fase 25 (Histórico) — Plataforma Enterprise e Marketplace
*Implementado: white-label, API keys, Cisco ASA/Palo Alto/Check Point*

| Funcionalidade | Detalhe |
|---|---|
| SSO | SAML 2.0 / OIDC — Azure AD, Okta, Google Workspace |
| RBAC granular | Permissões por cliente/dispositivo/operação (além dos 3 roles atuais) |
| API pública | OpenAPI 3.1 documentada — permite integrações externas e automações |
| White-label | Logo, cores e domínio customizados por tenant (revenda MSSP) |
| Multi-idioma | i18n/l10n — pt-BR ✅, en-US, es-LA |
| Billing | Planos, limites de devices, cobrança automatizada por tenant |
| Vendors enterprise | Cisco ASA/FTD, Palo Alto PAN-OS, Check Point R80+, Juniper SRX |
| Marketplace | Plugins de vendor contribuídos por comunidade / parceiros |

---

### Fase 26 — Golden Config Avançado: Template Bundles REST-native
*Implantação completa de filial com 1 clique — base + regras + filtro web + geo-IP + VPN*

**Contexto:** A Fase 17 faz Golden Config via CLI SSH (hostname, VLANs, interfaces, rotas). A Fase 26 estende para políticas de segurança completas gerenciadas via REST API nos firewalls modernos.

#### Modelo de dados

```
GoldenBundle
├── id, tenant_id, name, description, vendor
├── variables: JSONB          (variáveis globais do bundle)
└── sections: [BundleSection] (ordenadas por apply_order)

BundleSection
├── section_type: base_config | objects | access_rules | content_filter | geo_ip | vpn | sd_wan
├── template_id → GoldenTemplate   (CLI — Fase 17)
├── rest_payload_template: Text    (JSON com {VARIÁVEIS} para REST-native)
├── apply_strategy: cli_ssh | rest_api | manual_only
├── apply_order: int
└── rollback_strategy: snapshot_restore | delete_objects | none
```

**Herança de variáveis:** Bundle → Tenant → Device (device sempre sobrescreve)

#### Estratégias por vendor e seção

| section_type | Fortinet | SonicWall | pfSense | Sophos |
|---|---|---|---|---|
| base_config | CLI SSH | CLI SSH | CLI SSH | CLI SSH |
| objects | REST `/cmdb/firewall/address` | REST API | — | REST API |
| access_rules | REST `/cmdb/firewall/policy` | REST API | pfctl | REST API |
| content_filter | REST `/cmdb/webfilter/profile` | CFS REST | pfBlockerNG | REST API |
| geo_ip | REST `/cmdb/firewall/country` | Geo-IP REST | pfBlockerNG | REST API |
| vpn | REST `/cmdb/vpn.ipsec/phase1` | REST API | CLI SSH | REST API |
| sd_wan | REST `/cmdb/system/virtual-wan-link` | — | — | — |

#### Fluxo de aplicação

```
1. Snapshot automático pré-apply (fallback garantido)
2. Para cada seção (order_by apply_order):
   cli_ssh     → SSH + comandos CLI (executor Fase 17)
   rest_api    → FortinetRestConnector / SonicWallRestConnector
   manual_only → gera preview + aguarda aprovação humana
3. Falha em qualquer seção → rollback pela rollback_strategy da seção
4. Audit log imutável: seção, payload, resposta, status
```

#### Componentes a implementar

**Backend:** `golden_bundle.py` (model), `bundle_renderer.py`, `fortinet_rest_connector.py`, `sonicwall_rest_connector.py`, `bundle_worker.py` (Celery), `api/golden_bundle.py`

**Frontend:** `BundleEditor` (wizard), `BundleLibrary`, `BundleApplyModal` (polling), `BundleDiffView`

**Biblioteca embutida "Filial Padrão Fortinet":**
```
[1] base_config   → CLI: hostname, VLANs, interfaces, rotas
[2] objects       → REST: addr-objects RFC1918, DNS, trusted-nets
[3] access_rules  → REST: LAN→WAN allow, LAN→LAN isolado, WAN→all deny
[4] content_filter→ REST: webfilter (bloqueia P2P, adult, malware)
[5] geo_ip        → REST: bloqueia países de alto risco (lista por tenant)
[6] vpn           → REST: IPSec site-to-site ({PEER_IP}, {PSK}, {SUBNET})
```

---

### Fase 27 — Planejamento de Migração de Infraestrutura (VM Migration Planner)
*Planejamento assistido por IA — read-only, sem execução automatizada*

- Conectores read-only: VMware vCenter API, Proxmox API, Hyper-V (WinRM)
- Inventário de VMs: OS, CPU/RAM/disco, serviços em execução, dependências de rede
- Análise de dependências: mapa de comunicação entre VMs, ordem de migração sugerida
- IA gera runbook: sequência, janelas de manutenção, estratégia de rollback
- Export automático para BookStack

---

## Novos Vendors — Priorização

| Vendor | Categoria | Fase alvo | Prioridade | Status |
|---|---|---|---|---|
| Cisco ASA/FTD | Firewall | 25 | Alta | Pendente |
| Palo Alto PAN-OS | Firewall | 25 | Alta | Pendente |
| Check Point R80+ | Firewall | 25 | Alta | Pendente |
| Juniper SRX | Firewall | 25 | Média | Pendente |
| Huawei USG | Firewall | 25+ | Média | Pendente |
| TP-Link | Switch | 27+ | Baixa | Pendente |
| D-Link | Switch | 27+ | Baixa | Pendente |

**Implementados:** Sophos ✅ (F16), Intelbras/Juniper EX/Aruba ✅ (F15), HP Comware ✅ (F12), Dell N-Series ✅ (F11)

---

## Mapa de Dependências

```
Fase 1-13 (base)         ──► todas as fases subsequentes
Fase 14 (servidores)     ──► F20 (DBs) ──► F21 (offboard) ──► F22 (onboard)
Fase 15 (switches)       ──► F16 (firewall migration)
Fase 13 (variáveis)      ──► F17 (golden config) ──► F26 (bundles REST)
pgvector                 ──► F19 (RAG)
F21 + F22 (identidade)   ──► F23 (alertas: gatilhos offboard/onboard)
F21-23                   ──► F24 (dashboard executivo)
F24                      ──► F25 (enterprise/marketplace)
F26 pode rodar em paralelo com F25 (extensão vertical de F17)
F27 pode rodar em paralelo com F25-26 (módulo independente)

F28 (segurança + IA safety)  ──► F33 (governança IA) ──► F35 (SOAR)
F28 (hash-chained audit)     ──► F33 (ancoragem RFC 3161)
F29 (AI observability)       ──► F33 (red team + SIRP)
F31 (RBAC granular)          ──► F33 (four-eyes + aprovação dupla)
F34 (infra segurança)        pode rodar em paralelo com F33
F35 (SOAR) depende de F23 (alertas) + F33 (SIRP) + F34 (infra)
```
