# Eternity SecOps — Guia de Treinamento da Plataforma

> **Versão:** 0.1.0 · **Idioma:** Português Brasileiro · **Público-alvo:** Administradores, Analistas N2/N3, Gestores de TI

---

## Sumário

1. [O que é a Eternity SecOps](#1-o-que-é-a-eternity-secops)
2. [Conceitos Fundamentais](#2-conceitos-fundamentais)
3. [Papéis e Permissões](#3-papéis-e-permissões)
4. [Módulo: Firewalls](#4-módulo-firewalls)
5. [Módulo: Automação de Configuração](#5-módulo-automação-de-configuração)
6. [Módulo: Redes & Conectividade](#6-módulo-redes--conectividade)
7. [Módulo: Infraestrutura](#7-módulo-infraestrutura)
8. [Módulo: Identidade & Acesso](#8-módulo-identidade--acesso)
9. [Módulo: Inteligência (IA)](#9-módulo-inteligência-ia)
10. [Módulo: Segurança & Resposta](#10-módulo-segurança--resposta)
11. [Módulo: Relatórios](#11-módulo-relatórios)
12. [Módulo: Plataforma (Administração)](#12-módulo-plataforma-administração)
13. [Agente IA — Como Funciona](#13-agente-ia--como-funciona)
14. [Base de Conhecimento (RAG)](#14-base-de-conhecimento-rag)
15. [Arquitetura Multi-tenant / MSSP](#15-arquitetura-multi-tenant--mssp)
16. [Integrações e Ecosystem](#16-integrações-e-ecosystem)
17. [Fluxos de Trabalho Típicos](#17-fluxos-de-trabalho-típicos)
18. [Perguntas Frequentes](#18-perguntas-frequentes)

---

## 1. O que é a Eternity SecOps

A **Eternity SecOps** é uma plataforma MSSP (**Managed Security Service Provider**) para gestão centralizada de segurança de redes com Inteligência Artificial. Ela permite que times de TI e provedores de serviços gerenciem dezenas de firewalls, switches, servidores e identidades a partir de um único painel, com automação por IA para as tarefas mais repetitivas e análise proativa de riscos.

### Para quem é a plataforma?

| Perfil | Como usa |
|---|---|
| **Analista N2** | Gerencia dispositivos de firewall, inspeciona regras, executa operações CLI, responde alertas |
| **Analista N3** | Analisa servidores Linux/Windows, bancos de dados, troubleshooting avançado com IA |
| **Administrador de TI** | Define templates de configuração, gerencia grupos de dispositivos, controla usuários e permissões |
| **Gestor / Coordenador** | Acompanha dashboard executivo, score de risco, relatórios de conformidade |
| **MSSP / Revenda** | Gerencia múltiplos clientes (tenants) de forma isolada, com painel cross-tenant |

### Principais diferenciais

- **Agente IA nativo** — Converse em linguagem natural com qualquer dispositivo de rede
- **Multi-tenant isolado** — Cada cliente vê apenas seus próprios dados
- **Automação com audit trail** — Toda operação é rastreada e aprovável antes da execução
- **13+ vendors de firewall suportados** — Fortinet, Sophos, pfSense, OPNsense, MikroTik, Endian, Cisco ASA, Palo Alto, Check Point, Juniper SRX, Dell N-Series, HP Comware, Aruba e outros
- **Zero-touch para novos sites** — Um bundle aplica configuração completa de filial em 1 clique

---

## 2. Conceitos Fundamentais

### Tenant

Um **tenant** é um espaço isolado dentro da plataforma que representa um cliente ou organização. Todos os dados (dispositivos, usuários, alertas, relatórios) ficam completamente isolados entre tenants. Um usuário pertence a exatamente um tenant, exceto o Super Admin MSSP que enxerga todos.

### Device (Dispositivo)

Um **device** é qualquer equipamento de rede gerenciado pela plataforma: firewall, switch, servidor de borda. Cada device tem:
- **Credenciais de acesso** (IP, usuário, senha — armazenados criptografados)
- **Vendor** (Fortinet, pfSense, etc.) — define qual conector usar
- **Grupo** — permite aplicar operações em lote
- **Variáveis** — usadas em templates de configuração (herdam do tenant, sobrescrevem localmente)

### Operação

Uma **operação** é qualquer ação executada em um device: listar regras, aplicar template, iniciar sessão de agente IA, realizar snapshot. Cada operação gera um **log de auditoria** com quem executou, quando, o que foi feito e o resultado.

### Template

Um **template** é um bloco de comandos CLI parametrizado, com variáveis tipadas (`{HOSTNAME}`, `{VLAN_ID}`, `{IP_LAN}`). Pode ser reutilizado em qualquer device compatível com o vendor do template.

### Bundle

Um **bundle** é um conjunto ordenado de seções (base_config, regras, filtro web, VPN, geo-IP) que aplica uma configuração completa em um device. Pode combinar configuração via CLI SSH e via REST API do firewall.

### Score de Risco

O **score de risco** (0–100) é calculado pela plataforma com base em: dispositivos sem snapshot recente, regras permissivas (any/any), alertas críticos não resolvidos, conformidade com templates padrão, presença de vulnerabilidades detectadas. Quanto menor, melhor.

---

## 3. Papéis e Permissões

### Roles por Tenant

| Role | O que pode fazer |
|---|---|
| **admin** | Acesso total ao tenant: usuários, dispositivos, alertas, relatórios, aprovação de auditoria |
| **analyst** | Operar dispositivos, executar agente IA, ver relatórios — não gerencia usuários |
| **readonly** | Apenas visualização: dashboards, inventário, relatórios |

### Super Admin (MSSP)

O **Super Admin** é um usuário especial que:
- Acessa **todos** os tenants sem precisar ser membro de cada um
- Gerencia o painel MSSP com visão global de saúde e risco
- Configura plataforma (API keys, white-label, config. de plataforma)
- Aprova convites e gerencia o ecossistema de revendas

### Fluxo de convite de usuário

1. Admin do tenant acessa **Organização → Usuários → Convidar**
2. Informa o e-mail e o role desejado (admin/analyst/readonly)
3. O sistema envia um link de convite por e-mail
4. O usuário clica no link, define uma senha e entra na plataforma já vinculado ao tenant

---

## 4. Módulo: Firewalls

### 4.1 Dispositivos

**Acesso:** Menu → Firewalls → Dispositivos

Tela central de inventário de todos os firewalls do tenant. Cada dispositivo exibe:
- Status de conexão (testado em tempo real)
- Vendor e modelo
- Último snapshot
- Grupo(s) ao qual pertence

**Ações disponíveis:**
- **Adicionar device** — informar IP, credenciais, vendor, grupo
- **Testar conexão** — valida que as credenciais estão funcionando
- **Editar / Remover** — sempre registrado na auditoria
- **Definir variáveis locais** — sobrescrevem variáveis do tenant para esse device

### 4.2 Inspetor (Snapshot em Tempo Real)

**Acesso:** Menu → Firewalls → Inspetor

O Inspetor conecta ao device **ao vivo** e extrai:

| Aba | O que mostra |
|---|---|
| **Regras de Firewall** | Lista completa de políticas/access-control com source, destination, action, log |
| **NAT / PAT** | Regras de tradução de endereço (DNAT, SNAT, port-forward) |
| **Rotas** | Tabela de roteamento completa (estática, dinâmica) |
| **Interfaces** | Status de cada interface (IP, máscara, estado físico) |
| **BGP / OSPF** | Adjacências e sumário de rotas dinâmicas (quando disponível) |

**Como usar:**
1. Selecione o device no seletor
2. Clique em "Iniciar Snapshot"
3. A plataforma conecta via SSH/API e extrai as informações
4. Os dados ficam salvos como snapshot histórico para comparação futura

### 4.3 CLI Direto

**Acesso:** Menu → Firewalls → CLI Direto

Terminal interativo via SSH/API para executar comandos manualmente no device. Indicado para:
- Troubleshooting pontual
- Verificações que não têm tela específica
- Testes de conectividade (`ping`, `traceroute`)

**Importante:** Todo comando executado é logado na auditoria.

### 4.4 Operações em Lote (Bulk Jobs)

**Acesso:** Menu → Firewalls → Dispositivos → Selecionar múltiplos → Ação em Lote

Permite executar a mesma operação em vários devices simultaneamente:
- Aplicar template de configuração
- Iniciar snapshot
- Checar conformidade com template padrão
- Executar comando CLI

Os jobs em lote rodam em **background via Celery** (fila de tarefas). A tela exibe o progresso em tempo real com status por device.

---

## 5. Módulo: Automação de Configuração

### 5.1 Templates (Golden Config)

**Acesso:** Menu → Automação → Templates

Templates são blocos de configuração CLI reutilizáveis, com suporte a variáveis tipadas.

**Tipos de variável:**
- `string` — texto livre (ex: `{HOSTNAME}`)
- `ip` — validado como endereço IP (ex: `{IP_WAN}`)
- `int` — número inteiro (ex: `{VLAN_ID}`)
- `bool` — verdadeiro/falso
- `select` — lista de opções pré-definidas

**Herança de variáveis:**
```
Padrão do template (default)
    ↓ sobrescrito por
Variáveis do Tenant
    ↓ sobrescrito por
Variáveis do Device
```

**Como criar um template:**
1. Menu → Templates → Novo Template
2. Informar nome, vendor compatível e descrição
3. Escrever o bloco CLI com `{VARIAVEL}` nas posições parametrizáveis
4. Definir cada variável (tipo, descrição, valor default)
5. Salvar e associar a devices ou grupos

**Como aplicar um template:**
1. Na tela de Dispositivos, selecione o device
2. Ação → Aplicar Template
3. O sistema mostra os valores atuais das variáveis (herdados do tenant/device)
4. Ajuste se necessário e confirme
5. A plataforma gera o CLI final, faz SSH no device e aplica
6. O resultado é exibido na tela e salvo na auditoria

**Verificação de Divergência:**
A plataforma pode comparar a configuração atual do device com o template esperado e exibir o **diff**, indicando o que está fora do padrão.

### 5.2 Kits · Bundles

**Acesso:** Menu → Automação → Kits · Bundles

Bundles são conjuntos ordenados de seções de configuração para implantar um site completo.

**Seções disponíveis:**

| Seção | O que configura |
|---|---|
| `base_config` | Hostname, VLANs, interfaces, rotas estáticas |
| `objects` | Address-objects, grupos de endereços |
| `access_rules` | Políticas de firewall (LAN→WAN, isolamento, deny all) |
| `content_filter` | Perfil de filtro web (bloqueia P2P, adult, malware) |
| `geo_ip` | Bloqueio de países de alto risco |
| `vpn` | IPSec site-to-site com o concentrador central |
| `sd_wan` | Perfis de balanceamento SD-WAN (Fortinet) |

**Estratégias de aplicação:**
- **cli_ssh** — Comandos CLI via SSH (todos os vendors)
- **rest_api** — API REST nativa do firewall (Fortinet, Sophos, SonicWall)
- **manual_only** — Gera preview e aguarda aprovação humana antes de aplicar

**Fluxo de aplicação de bundle:**
1. Menu → Bundles → Selecionar bundle
2. Escolher device alvo
3. Informar variáveis específicas do site (IP do peer VPN, PSK, range de VLAN)
4. Revisar o preview de cada seção
5. Confirmar aplicação
6. A plataforma tira snapshot automático antes de aplicar (rollback garantido)
7. Aplica seção por seção em ordem
8. Em caso de falha, executa rollback automático da seção com problema

### 5.3 Importar Regras (Migração de Firewall)

**Acesso:** Menu → Automação → Importar Regras

Permite migrar regras de firewall de um vendor para outro, ou importar backup de configuração.

**Vendors suportados para importação:**
- Fortinet FortiOS (`.conf`)
- SonicWall (`.exp`)
- Sophos XG (`.tar`)

**Processo:**
1. Upload do arquivo de backup do firewall de origem
2. A plataforma faz parse e normaliza as regras para formato interno (IR — Intermediate Representation)
3. Exibe preview das regras interpretadas
4. Selecionar vendor de destino
5. A plataforma converte e gera o CLI de destino
6. Aplicar no device de destino (ou exportar como arquivo)

---

## 6. Módulo: Redes & Conectividade

### 6.1 Topologia & Rotas

**Acesso:** Menu → Redes & Conectividade → Topologia & Rotas

Visão consolidada da infraestrutura de rede do tenant.

**Funcionalidades:**

| Funcionalidade | Descrição |
|---|---|
| **Mapa de Topologia** | Grafo visual dos devices e suas conexões (baseado em rotas e interfaces) |
| **Tabelas de Roteamento** | Rota estática e dinâmica extraída via SSH de cada device |
| **BGP / OSPF** | Adjacências, AS number, redes anunciadas/recebidas |
| **SD-WAN** | Links configurados, métricas de qualidade (jitter, perda, latência) |
| **Cruzamento com Nmap** | IPs descobertos via scan cruzados com a tabela de rotas para identificar hosts não gerenciados |
| **Análise de Anomalias** | IA detecta rotas inesperadas, loops, black holes |

**Como usar:**
1. Menu → Topologia & Rotas
2. Clicar em "Sincronizar" para coletar dados atuais de todos os devices
3. O mapa é atualizado com as conexões detectadas
4. Clicar em qualquer device para ver seu detalhe de roteamento
5. Aba "Anomalias" lista os problemas detectados pela IA

### 6.2 Migração de Switches

**Acesso:** Menu → Redes & Conectividade → Migração de Switches

Módulo para documentar e migrar a configuração de switches de camada 2/3.

**Vendors suportados:**
- Juniper EX Series
- Aruba (HP ProCurve)
- Intelbras
- Dell N-Series (DNOS6)
- HP Comware (V1910)

**Processo de migração:**
1. Conectar ao switch de origem (SSH via Netmiko)
2. Extrair configuração atual (VLANs, trunks, spanning tree, ACLs)
3. Gerar documentação automática (publicada no BookStack, se integrado)
4. Adicionar switch de destino
5. A plataforma gera o CLI equivalente para o vendor de destino
6. Revisar e aplicar

---

## 7. Módulo: Infraestrutura

### 7.1 Servidores

**Acesso:** Menu → Infraestrutura → Servidores

Inventário de servidores Linux e Windows gerenciados pela plataforma.

**Como adicionar:**
- Linux: via SSH (usuário + chave ou senha)
- Windows: via WinRM (usuário + senha, com HTTPS)

**Dados coletados automaticamente:**
- OS, versão do kernel, uptime
- CPU, memória, disco (uso atual)
- Serviços em execução
- Pacotes desatualizados (Linux via `apt`/`yum`)
- Patches pendentes (Windows via WinRM)

### 7.2 Análise N3 (Analista de Servidores)

**Acesso:** Menu → Infraestrutura → Análise N3

Módulo de troubleshooting avançado assistido por IA para servidores.

**Funcionalidades:**
- **Análise de logs** — coleta logs de sistema e analisa com IA para identificar causa-raiz
- **Diagnóstico de performance** — CPU, memória, IO, processos top
- **Checklist de segurança** — portas abertas, usuários sem senha, SSH mal configurado
- **Integração Zabbix** — importa alertas ativos do Zabbix v6 e v7 e os analisa com IA
- **Integração Wazuh** — importa eventos de segurança e classifica por severidade

**Como usar:**
1. Selecionar servidor na lista
2. Clicar em "Iniciar Análise"
3. A plataforma conecta e coleta os dados
4. IA gera relatório com: diagnóstico, causa-raiz provável, ações recomendadas
5. O analista pode enviar comandos adicionais via Console SSH integrado

### 7.3 Console SSH

**Acesso:** Menu → Infraestrutura → Console SSH

Terminal SSH interativo para servidores (equivalente ao CLI Direto para firewalls). Todos os comandos são logados na auditoria.

### 7.4 Bancos de Dados

**Acesso:** Menu → Infraestrutura → Bancos de Dados

Conector de auditoria para bancos de dados de produção.

**Bancos suportados:**
- PostgreSQL
- MySQL / MariaDB
- SQL Server
- Oracle

**O que a plataforma audita:**
- Usuários existentes e seus privilégios
- Usuários sem senha ou com senha fraca
- Permissões excessivas (ex: `GRANT ALL` em usuário de aplicação)
- Usuários inativos há mais de 90 dias
- Conexões remotas permitidas (host)

**Análise por IA:** O agente analisa os dados coletados e gera um relatório de risco com recomendações específicas para o banco.

### 7.5 Migração de VMs

**Acesso:** Menu → Infraestrutura → Migração de VMs

Planejamento assistido por IA para migração de máquinas virtuais entre hypervisors.

**Hypervisors suportados (read-only):**
- VMware vCenter
- Proxmox
- Hyper-V (via WinRM)

**O que o módulo oferece:**
1. **Inventário automático** — lista todas as VMs com OS, CPU, memória, disco, serviços em execução
2. **Mapa de dependências** — identifica quais VMs se comunicam entre si (análise de tráfego)
3. **Ordem de migração** — sugere a sequência ideal para minimizar impacto
4. **Runbook gerado por IA** — documento completo com: etapas, janelas de manutenção, pré-requisitos, testes de validação, plano de rollback
5. **Export para BookStack** — publica o runbook na wiki da empresa automaticamente

**Importante:** O módulo é **somente leitura** — não executa a migração. O objetivo é o planejamento documentado.

---

## 8. Módulo: Identidade & Acesso

### 8.1 Identidade (Offboarding)

**Acesso:** Menu → Identidade & Acesso → Identidade

Módulo para gerenciar o ciclo de vida de usuários na saída da empresa.

**Integrações suportadas:**
- Azure Active Directory
- Google Workspace
- Active Directory Local (LDAP)
- SSH (chaves autorizadas em servidores Linux)
- WinRM (usuários Windows)
- Bancos de dados conectados
- Guacamole (sessões remotas)

**Processo de Offboarding:**
1. Buscar o colaborador pelo nome ou e-mail
2. A plataforma exibe todas as contas encontradas nas integrações ativas
3. Revisar a lista (pode deselecionar contas que não devem ser desativadas)
4. Confirmar — a plataforma desativa/remove as contas em todos os sistemas selecionados
5. Gera relatório de offboarding com timestamp de cada ação

**Contas Órfãs:**
A plataforma identifica automaticamente contas em sistemas que não correspondem a nenhum usuário ativo do tenant — indicando possíveis contas esquecidas.

**Webhook de RH:**
Permite integrar com sistemas de RH (ex: quando funcionário é demitido no sistema de RH, a plataforma recebe um webhook e inicia o offboarding automaticamente).

### 8.2 Onboarding

**Acesso:** Menu → Identidade & Acesso → Onboarding

Automação da criação de acessos para novos colaboradores.

**Perfis de Cargo:**
Cada cargo tem um perfil que define:
- Grupos do Active Directory a que deve pertencer
- Acesso ao GLPI (helpdesk)
- Acesso ao BookStack (wiki)
- Acesso ao SysPass (gestão de senhas)
- Permissões no Guacamole (acesso remoto)
- Configurações do Tactical RMM
- Perfil de VLAN no Unifi (acesso Wi-Fi)

**Processo de Onboarding:**
1. Informar nome, e-mail e cargo do novo colaborador
2. A plataforma exibe os acessos que serão criados (baseado no perfil do cargo)
3. Revisar e ajustar se necessário
4. Confirmar — a plataforma cria todos os acessos automaticamente
5. Gera relatório de onboarding com credenciais temporárias e instruções

---

## 9. Módulo: Inteligência (IA)

### 9.1 Agente IA

**Acesso:** Menu → Inteligência → Agente IA

Interface completa de chat com o agente inteligente vinculado a qualquer device do tenant.

**Também disponível como:** Botão flutuante no canto inferior direito de qualquer tela (drawer lateral), para acesso rápido sem sair da tela atual.

**Capacidades do agente:**
- Executar operações de leitura no device (listar regras, mostrar configuração, checar status de interface)
- Executar operações de escrita (após confirmação explícita do usuário)
- Responder perguntas sobre a configuração atual
- Sugerir melhorias de segurança
- Diagnosticar problemas com base nos dados do device
- Usar a Base de Conhecimento do tenant para contextualizar respostas

**Exemplos de perguntas:**
- "Liste as regras de firewall que permitem tráfego de qualquer origem"
- "Qual é o status do link WAN principal?"
- "Há alguma rota para 0.0.0.0/0 que não passe pelo gateway padrão?"
- "Compare a configuração atual com o template padrão de filial"

### 9.2 Base de Conhecimento

**Acesso:** Menu → Inteligência → Base de Conhecimento

Repositório de documentos que o Agente IA usa para contextualizar respostas.

**Formatos aceitos:**
- PDF
- DOCX (Word)
- Markdown (.md)

**Como funciona (RAG — Retrieval-Augmented Generation):**
1. Documento é enviado (upload)
2. A plataforma extrai o texto e divide em chunks
3. Cada chunk é transformado em embedding vetorial (OpenAI text-embedding)
4. Os embeddings ficam armazenados no banco vetorial (pgvector)
5. Quando o agente recebe uma pergunta, busca os chunks mais relevantes
6. Os chunks encontrados são injetados no contexto da conversa antes de chamar o Claude

**Documentos recomendados para upload:**
- Manual dos equipamentos de rede
- Políticas de segurança da empresa
- Topologia de rede documentada
- Runbooks e procedimentos internos
- Contratos de SLA com fornecedores

### 9.3 Conformidade

**Acesso:** Menu → Inteligência → Conformidade

Verificação automatizada de conformidade com padrões e templates.

**O que é verificado:**
- Divergência entre configuração atual e template padrão definido pelo admin
- Presença de regras permissivas (any/any allow)
- Regras sem log habilitado
- Interfaces sem IP documentado
- Dispositivos sem snapshot há mais de X dias

**Relatório de Conformidade:**
- Score por device (0–100%)
- Lista de desvios encontrados
- Sugestão de ação corretiva para cada desvio
- Histórico de evolução do score

### 9.4 Governança

**Acesso:** Menu → Inteligência → Governança

Visão agregada de governança de TI do tenant.

**Métricas disponíveis:**
- Total de devices gerenciados vs não gerenciados
- Cobertura de templates (% de devices com template aplicado)
- Frequência de operações (atividade por device e por usuário)
- Taxa de conformidade por grupo de devices
- Tempo médio entre snapshots
- Top 10 devices com mais operações

---

## 10. Módulo: Segurança & Resposta

### 10.1 Alertas

**Acesso:** Menu → Segurança & Resposta → Alertas

Central de alertas de segurança do tenant, com regras configuráveis.

**Gatilhos disponíveis:**
- Device offline por mais de X minutos
- Regra de firewall criada/modificada por usuário não autorizado
- Tentativas de login com falha repetidas
- Score de risco do tenant caiu abaixo de X
- Integração com Wazuh: alerta de severidade alta recebido
- Integração com Zabbix: alerta de host down
- Offboarding executado (confirmação)
- Onboarding de novo usuário

**Canais de notificação:**
- E-mail (SMTP)
- Slack (webhook)
- Microsoft Teams (webhook)
- Webhook genérico (HTTP POST com payload JSON)
- Jira (cria issue automaticamente)

**Como configurar um alerta:**
1. Menu → Alertas → Nova Regra
2. Selecionar gatilho
3. Definir condição (ex: "score < 50", "device offline > 10min")
4. Selecionar severidade (info / warning / critical)
5. Escolher canal(is) de notificação
6. Ativar a regra

**Histórico de alertas:**
Cada alerta disparado fica registrado no histórico com: timestamp, gatilho, dados do evento, canal notificado, status (ativo/resolvido).

### 10.2 Remediações

**Acesso:** Menu → Segurança & Resposta → Remediações

Fila de ações corretivas sugeridas pela plataforma.

**Como funciona:**
1. A IA detecta um problema (via alerta, análise de conformidade, ou análise de servidor)
2. Gera uma **remediação sugerida** com: descrição do problema, impacto, ação recomendada, comandos a executar
3. O analista revisa a remediação
4. Aprova, rejeita ou edita
5. Se aprovada, a ação é executada no device e logada na auditoria

---

## 11. Módulo: Relatórios

### 11.1 Dashboard Executivo

**Acesso:** Menu → Relatórios → Dashboard Executivo

Painel de alto nível para gestores e diretores.

**Métricas exibidas:**
- **Score de Risco Global** (0–100) — calculado sobre todos os devices e alertas ativos
- **Dispositivos monitorados** — total, online, offline, sem snapshot recente
- **Alertas ativos** — por severidade (crítico / aviso / info)
- **Conformidade média** — % de devices em conformidade com templates
- **Operações nas últimas 24h / 7d / 30d**
- **Top riscos** — lista dos principais problemas que penalizam o score

**Relatório PDF:**
Clique em "Exportar PDF" para gerar um relatório executivo formatado, pronto para apresentações à diretoria ou ao cliente. Inclui:
- Score de risco com gráfico de evolução
- Resumo executivo gerado por IA
- Tabela de devices e status
- Alertas críticos do período
- Recomendações prioritárias

### 11.2 Tickets IA (GLPI)

**Acesso:** Menu → Relatórios → Tickets IA

Integração com o GLPI (helpdesk) para análise inteligente de chamados.

**Funcionalidades:**
- Importa tickets abertos do GLPI
- Classifica por tipo (incidente / requisição / problema)
- IA sugere solução baseada na Base de Conhecimento
- Detecta tickets duplicados ou relacionados
- Gera relatório de tendências (assuntos mais recorrentes)

---

## 12. Módulo: Plataforma (Administração)

### 12.1 Auditoria

**Acesso:** Menu → Plataforma → Auditoria

Log imutável de todas as operações executadas na plataforma.

**O que é registrado:**
- Toda operação em device (quem, quando, o quê, resultado)
- Login e logout de usuários
- Criação/edição/remoção de usuários
- Aplicação de templates e bundles
- Aprovação ou rejeição de remediações
- Alterações de configuração da plataforma

**Aprovação de operações:**
Em tenants com política de aprovação ativa, operações de escrita em devices ficam em estado **pendente** até que um admin aprove. O badge vermelho na sidebar indica quantas aprovações estão aguardando.

**Filtros disponíveis:**
- Por usuário
- Por device
- Por tipo de operação
- Por período

**Export CSV** disponível para compliance e auditorias externas.

### 12.2 Enterprise

**Acesso:** Menu → Plataforma → Enterprise

Configurações de recursos enterprise do tenant.

**API Keys:**
- Gerencie chaves de API para integração com sistemas externos
- Cada chave tem escopos configuráveis (leitura, escrita, auditoria)
- Rotação de chaves com prazo de expiração

**White-label:**
- Logo personalizado do tenant
- Cores da marca
- Nome da plataforma customizado
- Domínio próprio (CNAME)

### 12.3 Configurações

**Acesso:** Menu → Plataforma → Configurações

Configurações pessoais do usuário logado:
- Alterar senha
- Preferências de notificação
- Fuso horário
- Idioma da interface

### 12.4 Config. de Plataforma

**Acesso:** Menu → Plataforma → Config. de Plataforma *(apenas Super Admin)*

Gerenciamento centralizado de chaves de API de serviços externos.

**Chaves gerenciáveis:**

| Serviço | Uso |
|---|---|
| `anthropic_api_key` | Agente IA (Claude) |
| `openai_api_key` | Embeddings da Base de Conhecimento |
| `smtp_host / smtp_port / smtp_user / smtp_password` | Envio de e-mails (convites, alertas, relatórios) |

**Como funciona:**
- As chaves ficam **armazenadas criptografadas** no banco de dados (Fernet AES-128)
- Se uma chave não estiver configurada no banco, a plataforma usa a variável de ambiente como fallback
- Há um cache de 5 minutos para evitar leituras excessivas ao banco

### 12.5 Organização

**Acesso:** Menu → Plataforma → Organização *(apenas admin e super admin)*

Gestão do tenant:
- **Usuários** — lista, convide, altere roles, desative usuários
- **Perfil do Tenant** — nome, logo, configurações globais
- **Variáveis do Tenant** — variáveis compartilhadas com todos os devices do tenant

### 12.6 Painel MSSP

**Acesso:** Menu → Plataforma → Painel MSSP *(apenas Super Admin)*

Visão cross-tenant do ambiente MSSP.

**O que o painel exibe:**
- Lista de todos os tenants com status de saúde
- Score de risco agregado por tenant
- Alertas críticos em qualquer tenant
- Operações executadas nas últimas 24h (volume por tenant)
- Tenants com devices offline
- Atividade recente de usuários

---

## 13. Agente IA — Como Funciona

### Arquitetura

```
Usuário → Interface Web → API Backend → Claude Sonnet 4.6 (Anthropic)
                               ↓
                   Executa operações no Device
                               ↓
                   Retorna resultado ao Claude
                               ↓
                   Claude formula resposta em linguagem natural
```

### Ciclo de uma conversa

1. **Usuário seleciona o device** — o agente sabe com qual equipamento vai interagir
2. **Usuário envia mensagem** — ex: "Liste as regras que permitem HTTP de qualquer origem"
3. **Backend cria operação** — com ID único (`operation_id`) para rastrear a conversa
4. **Claude interpreta** — decide qual ferramenta usar (list_rules, get_route_table, execute_cli, etc.)
5. **Backend executa** — conecta ao device real e coleta os dados
6. **Claude recebe os dados** — e formula a resposta em português, com análise e recomendações
7. **Usuário recebe resposta** — pode continuar a conversa com follow-up questions
8. **Contexto é mantido** — a conversa inteira é mantida no `operation_id` para continuidade

### Operações disponíveis para o agente

| Operação | O que faz |
|---|---|
| `list_firewall_rules` | Lista todas as regras/políticas do firewall |
| `list_nat_rules` | Lista regras de NAT/PAT |
| `get_route_table` | Extrai tabela de roteamento |
| `list_interfaces` | Status e endereços das interfaces |
| `execute_cli` | Executa comando CLI específico (quando necessário) |
| `get_device_info` | Versão de firmware, modelo, hostname |
| `search_knowledge_base` | Busca na Base de Conhecimento do tenant |

### Segurança do agente

- Toda operação de escrita requer **confirmação explícita** do usuário
- O agente **nunca executa** ações destrutivas sem aprovação
- Todas as chamadas ao device são registradas na **auditoria**
- O agente não tem acesso a dados de outros tenants

---

## 14. Base de Conhecimento (RAG)

### O que é RAG?

**RAG** (Retrieval-Augmented Generation) é a técnica que permite ao agente buscar informações relevantes nos documentos do tenant antes de formular uma resposta. Isso garante que o agente responda com o contexto específico da sua organização, não apenas com conhecimento genérico.

### Fluxo de ingestão de documento

```
Upload do arquivo
     ↓
Extração de texto (PDF/DOCX/MD)
     ↓
Divisão em chunks (~500 tokens cada)
     ↓
Geração de embedding (OpenAI text-embedding-3-small)
     ↓
Armazenamento no pgvector (banco vetorial)
```

### Fluxo de busca

```
Pergunta do usuário
     ↓
Geração de embedding da pergunta
     ↓
Busca por similaridade no pgvector (top 5 chunks mais próximos)
     ↓
Chunks injetados no contexto do Claude
     ↓
Claude responde com o contexto específico da empresa
```

### Boas práticas de uso

- **Nomeie bem os documentos** — o nome aparece na resposta do agente quando o documento é usado
- **Atualize documentos obsoletos** — remova versões antigas antes de enviar a nova
- **Prefira documentos em texto** — PDFs com imagens e tabelas complexas têm qualidade de extração menor
- **Tamanho máximo:** 50 MB por documento

---

## 15. Arquitetura Multi-tenant / MSSP

### Isolamento de dados

Cada tenant tem seus dados completamente isolados. O isolamento é garantido em todas as camadas:
- **Banco de dados:** todas as tabelas têm `tenant_id`, e toda query filtra por tenant
- **API:** cada endpoint valida que o objeto acessado pertence ao tenant do usuário autenticado
- **Credenciais:** armazenadas criptografadas com chave separada por tenant

### Modelo de permissões

```
Super Admin (MSSP)
  └── Tenant A
        ├── Admin A (role: admin)
        ├── Analista A (role: analyst)
        └── Visualizador A (role: readonly)
  └── Tenant B
        └── Admin B (role: admin)
```

### Herança de configurações

```
Plataforma (Super Admin)
  └── Tenant (variáveis globais do cliente)
        └── Device (variáveis locais do equipamento)
```

Quando uma variável de template é buscada, a ordem de prioridade é: **device > tenant > padrão do template**.

---

## 16. Integrações e Ecosystem

### Integrações de identidade

| Sistema | Protocolo | Para que serve |
|---|---|---|
| Azure Active Directory | Graph API | Onboarding/Offboarding de usuários |
| Google Workspace | Admin SDK | Onboarding/Offboarding |
| Active Directory Local | LDAP | Onboarding/Offboarding |
| Guacamole | API REST | Acesso remoto (criação de conexões) |
| Tactical RMM | API REST | Endpoint management |
| Unifi | API REST | Perfil de VLAN/Wi-Fi |

### Integrações de monitoramento

| Sistema | Para que serve |
|---|---|
| Zabbix v6 / v7 | Importar alertas, status de hosts |
| Wazuh | Importar eventos de segurança |
| Nmap | Descoberta de hosts e serviços |
| Shodan | Inteligência sobre IPs expostos |
| OpenVAS | Scan de vulnerabilidades |
| Prometheus + Grafana | Observabilidade da própria plataforma |

### Integrações de notificação e tickets

| Sistema | Para que serve |
|---|---|
| E-mail (SMTP) | Alertas, convites, relatórios |
| Slack | Alertas em tempo real |
| Microsoft Teams | Alertas em tempo real |
| Jira | Criação automática de issues |
| Webhook genérico | Integração com qualquer sistema |
| GLPI | Tickets e análise IA |
| BookStack | Publicação automática de documentação |
| SysPass | Gestão de senhas |

### Vendors de firewall suportados

| Vendor | Método de conexão |
|---|---|
| Fortinet FortiGate | SSH CLI + REST API |
| Sophos XG / SFOS | REST API + SSH |
| pfSense | SSH + pfctl |
| OPNsense | SSH + API |
| MikroTik RouterOS | SSH (RouterOS CLI) |
| Endian Firewall | SSH CLI |
| Cisco ASA / FTD | SSH CLI |
| Palo Alto PAN-OS | REST API |
| Check Point R80+ | SSH + API |
| Juniper SRX | SSH CLI |
| Dell N-Series (DNOS6) | SSH via Netmiko |
| HP Comware (V1910) | SSH via Netmiko |
| Aruba | SSH CLI |

---

## 17. Fluxos de Trabalho Típicos

### Fluxo 1 — Adicionar um novo cliente (MSSP)

1. Super Admin acessa Painel MSSP → Criar Tenant
2. Informa nome do cliente, logo e configurações iniciais
3. Cria o usuário admin do cliente (ou convida via e-mail)
4. Define variáveis globais do tenant (ex: range de IP da rede, servidor DNS)
5. O admin do cliente faz login e começa a adicionar seus devices

### Fluxo 2 — Primeiro device de um cliente

1. Admin do tenant → Dispositivos → Adicionar Device
2. Informa IP, usuário, senha, vendor
3. Testa a conexão (botão "Testar")
4. Configura variáveis locais do device se necessário
5. Executa primeiro snapshot (Inspetor → Iniciar Snapshot)
6. Configura alertas de "device offline"
7. Executa primeira verificação de conformidade

### Fluxo 3 — Responder a um alerta crítico

1. Analista recebe notificação (Slack / e-mail) com link direto ao alerta
2. Acessa a tela de Alertas → clica no alerta
3. Vê detalhes: device afetado, gatilho, timestamp, dados do evento
4. Clica em "Investigar com IA" — abre o Agente IA com contexto do alerta já injetado
5. O agente faz diagnóstico inicial automaticamente
6. Analista faz perguntas de follow-up
7. Agente sugere remediação
8. Analista aprova a remediação → é executada no device
9. Analista marca o alerta como resolvido com nota

### Fluxo 4 — Implantar nova filial

1. Admin cria novo device com as credenciais do firewall da filial
2. Testa conexão
3. Vai em Bundles → seleciona "Filial Padrão Fortinet" (ou template do cliente)
4. Informa variáveis específicas: IP WAN, range de VLAN local, IP do concentrador VPN
5. Revisa o preview de cada seção
6. Inicia aplicação — a plataforma:
   a. Tira snapshot do estado atual
   b. Aplica base_config (hostname, VLANs, interfaces)
   c. Aplica objects (address-objects)
   d. Aplica access_rules (políticas LAN→WAN, bloqueios)
   e. Aplica content_filter (filtro web)
   f. Aplica geo_ip (bloqueio de países)
   g. Aplica vpn (IPSec site-to-site)
7. Resultado exibido em tempo real por seção
8. Snapshot pós-apply é registrado automaticamente
9. Score de conformidade do device atualizado

### Fluxo 5 — Offboarding de colaborador demitido

1. RH notifica via webhook (ou analista acessa manualmente)
2. Menu → Identidade → buscar pelo nome/e-mail
3. Plataforma lista todas as contas encontradas: AD, Google, SSH, banco de dados, Guacamole
4. Analista revisa (pode deselecionar conta pessoal que não deve ser desativada)
5. Confirma offboarding
6. Plataforma desativa/remove as contas em todos os sistemas
7. Relatório de offboarding gerado com log de cada ação
8. Alerta de "offboarding executado" disparado para o admin

### Fluxo 6 — Gerar relatório executivo mensal

1. Acessa Dashboard Executivo
2. Seleciona período (mês anterior)
3. Revisa o score de risco e as métricas exibidas
4. Clica em "Exportar PDF"
5. O PDF é gerado com: score, gráficos de evolução, resumo por IA, alertas do período, recomendações
6. Envia para diretoria / cliente

---

## 18. Perguntas Frequentes

**P: Como a plataforma armazena as senhas dos firewalls?**
R: As credenciais são criptografadas com AES-128 (Fernet) antes de serem gravadas no banco de dados. Nunca são armazenadas em texto puro.

**P: O agente IA pode modificar a configuração do firewall sem eu pedir?**
R: Não. Toda operação de escrita requer confirmação explícita do usuário. O agente pergunta antes de executar qualquer mudança.

**P: O que acontece se o Anthropic (Claude) estiver fora do ar?**
R: Todas as operações que não dependem de IA (snapshot, CLI direto, listagem de regras, alertas) continuam funcionando normalmente. Apenas o Agente IA e a geração de relatórios com texto ficam indisponíveis.

**P: Posso usar a plataforma para gerenciar firewalls em redes com NAT/CGNAT?**
R: A versão atual requer acesso direto ao IP do device (inbound). O suporte a Edge Agent (conexão de saída, sem porta inbound) está planejado para a Fase 31.

**P: Quantos devices posso adicionar?**
R: Depende do plano contratado. Entre em contato com o suporte para verificar os limites do seu plano.

**P: Como faço para exportar todos os meus dados se quiser sair da plataforma?**
R: Acesse Configurações → Exportar Dados (em desenvolvimento — disponível na Fase 30). Enquanto isso, o suporte pode fornecer um dump completo dos seus dados mediante solicitação.

**P: O log de auditoria pode ser apagado?**
R: Não. O log de auditoria é imutável — nenhum usuário, nem mesmo o Super Admin, pode apagar ou editar entradas de auditoria.

**P: Como funciona o score de risco?**
R: O score (0–100, menor = pior) considera: dispositivos sem snapshot recente, regras permissivas (any/any allow), alertas críticos não resolvidos, desvios de templates padrão, e vulnerabilidades detectadas pelas integrações de scan. O peso de cada fator é configurável por tenant.

**P: A plataforma atende LGPD?**
R: A plataforma implementa as salvaguardas técnicas (criptografia, controle de acesso, log de auditoria, isolamento de dados). Para conformidade LGPD completa, são necessários também os processos e contratos adequados (DPA). Consulte o time jurídico para o mapeamento completo.

**P: Posso integrar com meu sistema de helpdesk que não é GLPI?**
R: Sim, via Webhook genérico ou via Jira. Para outros sistemas, entre em contato com o suporte para avaliar integração customizada.

---

*Documento gerado em: 2026-05-09 · Plataforma: Eternity SecOps v0.1.0*
