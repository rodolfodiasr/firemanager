export type ModuleStatus = "ga" | "beta" | "coming_soon";

export interface ModuleHelp {
  slug: string;
  title: string;
  section: string;
  status: ModuleStatus;
  description: string;
  howToUse: string[];
  tip?: string;
}

// Indexado pela rota exata do React Router
export const helpByRoute: Record<string, ModuleHelp> = {

  // ── Início ──────────────────────────────────────────────────────────────────
  "/": {
    slug: "dashboard",
    title: "Dashboard",
    section: "Início",
    status: "ga",
    description:
      "Visão geral da saúde operacional da plataforma. Exibe métricas em tempo real de dispositivos, alertas ativos, operações recentes e postura de segurança consolidada de todos os ativos monitorados.",
    howToUse: [
      "Verifique os cartões de resumo no topo para identificar rapidamente problemas críticos.",
      "Clique em qualquer métrica para navegar direto ao módulo correspondente.",
      "Use o filtro de período para comparar métricas entre janelas de tempo.",
      "Monitore o gráfico de tendência de alertas para identificar padrões.",
    ],
    tip: "O Dashboard atualiza automaticamente a cada 30 segundos. Não é necessário recarregar a página.",
  },

  "/executive": {
    slug: "dashboard-executivo",
    title: "Dashboard Executivo",
    section: "Início",
    status: "ga",
    description:
      "Painel de KPIs estratégicos voltado para gestores e diretoria. Consolida SLAs, índice de conformidade, MTTR médio, cobertura de ativos e tendências de risco em uma visão única de alto nível.",
    howToUse: [
      "Selecione o período de análise (mês, trimestre, ano) no filtro superior.",
      "Exporte os dados como PDF ou CSV para apresentações executivas.",
      "Compare o desempenho atual com períodos anteriores nos gráficos de tendência.",
      "Monitore o índice de conformidade para acompanhar auditorias regulatórias.",
    ],
    tip: "Os dados do Dashboard Executivo são calculados a partir de todas as fontes da plataforma e podem ter latência de até 1 hora.",
  },

  // ── Firewalls ────────────────────────────────────────────────────────────────
  "/devices": {
    slug: "dispositivos",
    title: "Dispositivos",
    section: "Firewalls",
    status: "ga",
    description:
      "Central de gerenciamento de firewalls, roteadores e dispositivos de rede. Permite cadastrar ativos, aplicar configurações em massa, gerenciar grupos de dispositivos, variáveis de ambiente e importar regras de outros fornecedores.",
    howToUse: [
      "Clique em '+ Adicionar Dispositivo' para cadastrar um novo firewall com IP, credenciais e modelo.",
      "Use a aba 'Grupos' para agrupar dispositivos por filial, função ou criticidade.",
      "Na aba 'Variáveis', defina valores reutilizáveis (ex: IP do gateway, VLAN padrão) que podem ser referenciados em templates.",
      "Selecione múltiplos dispositivos e use 'Operação em Massa' para aplicar configurações simultâneas.",
      "O indicador de saúde (verde/amarelo/vermelho) reflete o último ping e status de conexão.",
    ],
    tip: "Use variáveis com a sintaxe {{nome_variavel}} nos templates para parametrizar configurações por ambiente.",
  },

  "/inspector": {
    slug: "inspetor",
    title: "Inspetor de Regras",
    section: "Firewalls",
    status: "ga",
    description:
      "Analisa as regras de firewall existentes para identificar inconsistências, regras redundantes, permissões excessivamente abertas e desvios de boas práticas de segurança. Gera recomendações priorizadas por risco.",
    howToUse: [
      "Selecione o dispositivo a ser inspecionado no filtro superior.",
      "Clique em 'Executar Análise' para iniciar a varredura das regras atuais.",
      "Revise as recomendações organizadas por severidade (Crítico, Alto, Médio, Baixo).",
      "Clique em cada recomendação para ver o contexto da regra afetada e a ação sugerida.",
      "Use 'Aplicar Correção' para implementar a recomendação diretamente via agente.",
    ],
    tip: "Execute o Inspetor após importar regras de outro fornecedor para garantir conformidade antes de colocar em produção.",
  },

  "/agent": {
    slug: "agente-firewall",
    title: "Agente · Firewall",
    section: "Firewalls",
    status: "ga",
    description:
      "Assistente de IA especializado em configuração e diagnóstico de firewalls. Interpreta comandos em linguagem natural e os traduz para ações reais nos dispositivos selecionados, com plano de ação revisável antes da execução.",
    howToUse: [
      "Selecione o dispositivo alvo no painel lateral antes de enviar comandos.",
      "Descreva o que deseja fazer em português, ex: 'Bloqueie o tráfego da rede 192.168.5.0/24 para a porta 443'.",
      "Revise o plano de ação gerado pelo agente antes de confirmar a execução.",
      "Use o painel de diagnóstico para ver o output real do dispositivo após cada operação.",
      "O histórico de comandos fica disponível na aba Auditoria.",
    ],
    tip: "O agente nunca executa ações sem confirmação explícita. Sempre revise o plano de ação exibido.",
  },

  // ── Automação ────────────────────────────────────────────────────────────────
  "/golden-templates": {
    slug: "templates",
    title: "Templates de Configuração",
    section: "Automação",
    status: "ga",
    description:
      "Biblioteca de templates reutilizáveis de configuração de firewall. Permite criar, versionar e aplicar configurações padronizadas em múltiplos dispositivos com suporte a variáveis parametrizáveis.",
    howToUse: [
      "Clique em '+ Novo Template' e escolha o fabricante (Cisco, Fortinet, pfSense, etc.).",
      "Escreva a configuração usando variáveis com sintaxe {{nome}} para torná-la reutilizável.",
      "Salve e teste o template em um dispositivo de homologação antes de aplicar em produção.",
      "Na aba 'Aplicar', selecione os dispositivos de destino e preencha os valores das variáveis.",
      "Acompanhe o resultado da aplicação em tempo real via log de operação.",
    ],
    tip: "Templates são versionados automaticamente. É possível reverter para versões anteriores a qualquer momento.",
  },

  "/golden-bundles": {
    slug: "kits-bundles",
    title: "Kits · Bundles",
    section: "Automação",
    status: "ga",
    description:
      "Agrupa múltiplos templates em um pacote de configuração completo (bundle) que pode ser aplicado de uma vez. Útil para onboarding de novos sites, padronização de filiais ou implantação de políticas de segurança em lote.",
    howToUse: [
      "Clique em '+ Novo Bundle' e dê um nome descritivo (ex: 'Padrão Filial 2024').",
      "Adicione os templates desejados ao bundle na ordem em que devem ser aplicados.",
      "Defina valores padrão para as variáveis compartilhadas entre os templates.",
      "Aplique o bundle em múltiplos dispositivos de uma só vez via 'Aplicar Bundle'.",
    ],
    tip: "Bundles são ideais para padronizar novos sites: crie um bundle padrão e aplique-o durante o onboarding de cada nova filial.",
  },

  "/firewall-migrations": {
    slug: "importar-regras",
    title: "Importar Regras",
    section: "Automação",
    status: "ga",
    description:
      "Importa e converte configurações de regras de firewall de outros fabricantes (Cisco ASA, Check Point, Palo Alto, iptables, etc.) para o formato do dispositivo de destino. Detecta conflitos e regras incompatíveis automaticamente.",
    howToUse: [
      "Selecione o fabricante de origem e faça upload do arquivo de configuração exportado.",
      "Aguarde a análise automática de conversão — o sistema mapeia as regras para o formato de destino.",
      "Revise os itens sinalizados como 'Requer revisão manual' antes de prosseguir.",
      "Selecione o dispositivo de destino e clique em 'Importar Regras Aprovadas'.",
      "Execute o Inspetor de Regras após a importação para validar a postura de segurança.",
    ],
  },

  // ── Redes & Conectividade ────────────────────────────────────────────────────
  "/connectivity": {
    slug: "topologia-rotas",
    title: "Topologia & Rotas",
    section: "Redes & Conectividade",
    status: "ga",
    description:
      "Mapa visual da topologia de rede com descoberta automática de dispositivos, rotas, VLANs e segmentos. Permite visualizar o caminho de tráfego entre endpoints e identificar pontos de falha ou gargalos.",
    howToUse: [
      "Clique em 'Descobrir Rede' para iniciar a varredura automática de dispositivos conectados.",
      "Arraste os nós no mapa para organizar a visualização conforme a topologia física.",
      "Clique em um link entre dispositivos para ver detalhes de rotas, latência e utilização.",
      "Use filtros por VLAN ou segmento para isolar partes específicas da rede.",
    ],
  },

  "/migrations": {
    slug: "migracao-switches",
    title: "Migração de Switches",
    section: "Redes & Conectividade",
    status: "ga",
    description:
      "Gerencia o processo de migração de configurações entre switches de diferentes fabricantes ou modelos. Converte VLANs, ACLs, trunks e configurações de spanning tree para o formato de destino.",
    howToUse: [
      "Selecione o switch de origem e exporte sua configuração atual.",
      "Faça upload da configuração e selecione o modelo de destino.",
      "Revise o mapeamento de VLANs e interfaces gerado automaticamente.",
      "Aplique a configuração convertida no switch de destino após validação.",
    ],
  },

  "/network-agent": {
    slug: "agente-redes",
    title: "Agente · Redes",
    section: "Redes & Conectividade",
    status: "ga",
    description:
      "Assistente de IA para diagnóstico e configuração de infraestrutura de redes. Analisa problemas de conectividade, sugere ajustes de roteamento e executa configurações em switches e roteadores via linguagem natural.",
    howToUse: [
      "Descreva o problema de rede em português, ex: 'A VLAN 30 não consegue acessar o servidor 10.0.1.50'.",
      "O agente executa diagnóstico automático (ping, traceroute, análise de rotas) e apresenta o resultado.",
      "Revise a ação proposta e confirme para que o agente aplique a correção.",
    ],
  },

  // ── Infraestrutura ────────────────────────────────────────────────────────────
  "/servers": {
    slug: "servidores",
    title: "Servidores",
    section: "Infraestrutura",
    status: "ga",
    description:
      "Inventário e monitoramento de servidores físicos e virtuais. Exibe métricas de CPU, memória, disco e rede em tempo real, além de alertas de saúde e histórico de eventos por servidor.",
    howToUse: [
      "Cadastre servidores com IP, credenciais SSH ou agente instalado.",
      "Monitore as métricas de recurso em tempo real no painel de cada servidor.",
      "Configure alertas de limiar (ex: CPU > 90% por mais de 5 minutos).",
      "Acesse o terminal SSH diretamente pelo módulo 'Agente · Servidores' para diagnóstico remoto.",
    ],
  },

  "/server-analysis": {
    slug: "agente-servidores",
    title: "Agente · Servidores",
    section: "Infraestrutura",
    status: "ga",
    description:
      "Assistente de IA para análise, diagnóstico e automação de servidores. Interpreta logs, identifica causas raiz de problemas de performance e executa scripts de remediação com aprovação do operador.",
    howToUse: [
      "Selecione o servidor alvo no painel lateral.",
      "Descreva o problema ou solicite uma análise, ex: 'Por que o servidor está com alta utilização de CPU?'",
      "O agente analisa logs, processos e métricas e apresenta a causa raiz identificada.",
      "Confirme a ação sugerida para executar a remediação automaticamente.",
    ],
    tip: "O agente tem acesso somente leitura por padrão. Ações de escrita requerem confirmação explícita a cada execução.",
  },

  "/database-connectors": {
    slug: "bancos-de-dados",
    title: "Bancos de Dados",
    section: "Infraestrutura",
    status: "ga",
    description:
      "Gerencia conectores para bancos de dados relacionais e NoSQL. Permite testar conectividade, monitorar saúde, auditar queries executadas e integrar informações de BD com análises da plataforma.",
    howToUse: [
      "Clique em '+ Novo Conector' e preencha host, porta, usuário e senha do banco.",
      "Use 'Testar Conexão' para validar as credenciais antes de salvar.",
      "Monitore métricas de conexão ativa, queries lentas e erros na aba de saúde do conector.",
    ],
  },

  "/vm-migration": {
    slug: "migracao-vms",
    title: "Migração de VMs",
    section: "Infraestrutura",
    status: "ga",
    description:
      "Orquestra migrações de máquinas virtuais entre hypervisors (VMware, Hyper-V, KVM) ou para a nuvem. Realiza análise de compatibilidade prévia, agendamento de janelas e acompanhamento do progresso em tempo real.",
    howToUse: [
      "Selecione a VM de origem e o hypervisor de destino.",
      "Execute a análise de compatibilidade para identificar possíveis impedimentos.",
      "Agende a migração para uma janela de manutenção aprovada.",
      "Acompanhe o progresso e receba notificação ao concluir.",
    ],
  },

  "/rmm": {
    slug: "rmm",
    title: "RMM",
    section: "Infraestrutura",
    status: "beta",
    description:
      "Integração com plataformas de Remote Monitoring and Management (Tactical RMM, N-able, etc.). Sincroniza inventário de endpoints, recebe alertas de agentes RMM e permite executar scripts remotos a partir da plataforma.",
    howToUse: [
      "Configure a integração com seu RMM em Configurações > Integrações.",
      "Após sincronização, os endpoints aparecem automaticamente no inventário.",
      "Monitore alertas provenientes do RMM na Central de Alertas.",
      "Execute scripts remotos nos endpoints diretamente pelo módulo.",
    ],
    tip: "Este módulo está em Beta. Algumas funcionalidades podem estar incompletas ou mudar sem aviso prévio.",
  },

  "/cloud-posture": {
    slug: "cloud-posture",
    title: "Cloud Posture",
    section: "Infraestrutura",
    status: "ga",
    description:
      "Avalia a postura de segurança de ambientes de nuvem (AWS, Azure, GCP). Identifica recursos mal configurados, exposições públicas indevidas, permissões excessivas e desvios de benchmarks CIS e NIST.",
    howToUse: [
      "Conecte sua conta de nuvem via chave de acesso ou role de serviço com permissão de leitura.",
      "Execute uma varredura de postura para obter o relatório inicial.",
      "Priorize as falhas por severidade e clique em cada item para ver o recurso afetado e a correção sugerida.",
      "Configure varreduras periódicas automáticas na aba de agendamento.",
    ],
  },

  // ── Identidade & Acesso ───────────────────────────────────────────────────────
  "/identity": {
    slug: "identidade",
    title: "Identidade",
    section: "Identidade & Acesso",
    status: "ga",
    description:
      "Central de gerenciamento de identidades. Sincroniza usuários e grupos do Active Directory (on-premise e Azure AD/Entra ID), exibe o inventário de contas, detecta anomalias de acesso e gerencia ciclo de vida de identidades.",
    howToUse: [
      "Configure a integração com seu AD/LDAP em Configurações > Integrações para iniciar a sincronização.",
      "Use a busca para localizar usuários por nome, e-mail ou grupo.",
      "Revise o painel de anomalias para contas inativas, senhas expiradas e admins sem MFA.",
      "Acione um fluxo de revisão de acesso para desprovisionar usuários que não deveriam mais ter acesso.",
    ],
  },

  "/selfservice-portal": {
    slug: "self-service-portal",
    title: "Self-Service Portal",
    section: "Identidade & Acesso",
    status: "beta",
    description:
      "Portal de autoatendimento para solicitação e aprovação de acessos a grupos do Active Directory e recursos de TI. O admin aprova a solicitação e o sistema provisiona automaticamente o usuário no grupo AD correspondente.",
    howToUse: [
      "Na aba 'Catálogo', cadastre os grupos AD ou recursos disponíveis para solicitação.",
      "Usuários submetem solicitações pelo portal com justificativa de negócio.",
      "Na aba 'Solicitações', revise os pedidos pendentes e clique em 'Aprovar' ou 'Rejeitar'.",
      "Ao aprovar, o sistema adiciona o usuário ao grupo AD imediatamente (via LDAP ou Microsoft Graph).",
      "Use a aba 'Relatórios AD' para auditar senhas expiradas, contas inativas e admins sem MFA.",
    ],
    tip: "O provisionamento é imediato após aprovação — não há fila de processamento. O botão 'Provisionar' executa a ação no AD em tempo real.",
  },

  "/edge-agents": {
    slug: "edge-agents-sso",
    title: "Edge Agents & SSO",
    section: "Identidade & Acesso",
    status: "beta",
    description:
      "Gerencia agentes de borda instalados em filiais e sites remotos para coleta de dados locais, além da configuração de Single Sign-On (SSO) para integração com provedores de identidade (SAML 2.0, OIDC).",
    howToUse: [
      "Baixe e instale o agente de borda no servidor local da filial seguindo o guia de instalação.",
      "Após instalação, o agente aparece automaticamente na lista com status de conexão.",
      "Para SSO, configure o provedor de identidade (Azure AD, Okta, etc.) na aba 'Configuração SSO'.",
      "Teste o fluxo de autenticação com um usuário de teste antes de habilitar para todos.",
    ],
  },

  // ── Segurança & Resposta ───────────────────────────────────────────────────────
  "/alerts": {
    slug: "alertas-siem",
    title: "Alertas & SIEM",
    section: "Segurança & Resposta",
    status: "ga",
    description:
      "Central unificada de alertas de segurança e integração com SIEMs (Splunk, Elastic SIEM, Microsoft Sentinel). Normaliza eventos de múltiplas fontes, correlaciona incidentes e permite triagem e escalonamento.",
    howToUse: [
      "Configure as integrações com seu SIEM em Configurações > Integrações SIEM.",
      "Filtre alertas por severidade, fonte ou status (aberto, em análise, resolvido).",
      "Clique em um alerta para ver o contexto completo do evento e a linha do tempo.",
      "Atribua o alerta a um analista ou escale para N2 diretamente pelo painel.",
      "Crie playbooks SOAR para automatizar respostas a padrões de alerta recorrentes.",
    ],
  },

  "/remediation": {
    slug: "remediacoes",
    title: "Remediações",
    section: "Segurança & Resposta",
    status: "ga",
    description:
      "Gerencia o ciclo de vida de remediações de vulnerabilidades e não-conformidades. Cria planos de ação, atribui responsáveis, acompanha prazos e integra com sistemas de tickets (Jira, GLPI) para rastreabilidade.",
    howToUse: [
      "Crie uma remediação a partir de um alerta, achado de compliance ou vulnerabilidade identificada.",
      "Defina responsável, prazo e prioridade para cada item.",
      "Acompanhe o progresso no quadro Kanban (Aberto > Em andamento > Validação > Concluído).",
      "Vincule evidências de correção (screenshots, logs, tickets) antes de marcar como concluído.",
      "Relatórios de SLA mostram itens vencidos e taxa de remediação no período.",
    ],
  },

  "/playbooks": {
    slug: "soar-playbooks",
    title: "SOAR Playbooks",
    section: "Segurança & Resposta",
    status: "ga",
    description:
      "Motor de automação de resposta a incidentes. Define gatilhos de segurança (anomalia, alerta SIEM, violação de SoD, device sem resposta) e executa ações em cadeia automaticamente: notificar, desabilitar conta AD, revogar acesso JIT, isolar dispositivo, criar ticket.",
    howToUse: [
      "Clique em '+ Novo Playbook' e escolha o tipo de gatilho (ex: 'Anomalia de Identidade').",
      "Use o Builder Visual para adicionar e conectar ações no canvas drag-and-drop.",
      "Configure o cooldown (tempo mínimo entre execuções) para evitar loops.",
      "Ative o playbook com o toggle — ele será avaliado automaticamente a cada 60 segundos.",
      "Monitore execuções anteriores e o MTTR na aba 'MTTR'.",
      "Use 'Carregar Templates AD' para importar 5 playbooks pré-construídos para cenários comuns.",
    ],
    tip: "Ações críticas (desabilitar conta AD, isolar dispositivo) executam imediatamente após o gatilho ser detectado — sem aprovação manual. Configure o cooldown adequadamente.",
  },

  // ── Conformidade ────────────────────────────────────────────────────────────────
  "/compliance": {
    slug: "compliance",
    title: "Compliance",
    section: "Conformidade",
    status: "ga",
    description:
      "Central de conformidade regulatória. Avalia a aderência a frameworks como ISO 27001, LGPD, CIS Controls, NIST CSF e PCI DSS. Gera evidências, rastreia desvios e produz relatórios de auditoria.",
    howToUse: [
      "Selecione o framework de conformidade aplicável à sua organização.",
      "Execute a avaliação automática — o sistema mapeia controles para evidências coletadas da plataforma.",
      "Revise os controles com status 'Não Conforme' e crie remediações diretamente pelo painel.",
      "Exporte o relatório de conformidade em PDF para apresentar a auditores.",
      "Configure avaliações periódicas automáticas para manter o status sempre atualizado.",
    ],
  },

  // ── Inteligência IA ─────────────────────────────────────────────────────────────
  "/knowledge": {
    slug: "base-de-conhecimento",
    title: "Base de Conhecimento",
    section: "Inteligência IA",
    status: "ga",
    description:
      "Repositório centralizado de documentos técnicos, runbooks e procedimentos que alimenta o Assistente IA. Documentos indexados são usados como contexto nas respostas do assistente, tornando-o específico para o seu ambiente.",
    howToUse: [
      "Clique em '+ Novo Documento' e faça upload de PDFs, DOCs ou cole o conteúdo diretamente.",
      "Organize documentos por categoria (Runbooks, Políticas, Procedimentos, etc.).",
      "Após upload, aguarde o processamento de indexação — o documento fica disponível para o assistente em minutos.",
      "Use a busca semântica para localizar documentos por conteúdo, não apenas por título.",
    ],
    tip: "Quanto mais documentos do seu ambiente estiverem na base, mais precisas e contextualizadas serão as respostas do Assistente IA.",
  },

  "/assistant": {
    slug: "assistente-ia",
    title: "Assistente IA",
    section: "Inteligência IA",
    status: "ga",
    description:
      "Assistente conversacional especializado em segurança e infraestrutura. Combina o conhecimento dos documentos da Base de Conhecimento com capacidade de análise técnica para responder perguntas, redigir documentos e diagnosticar problemas.",
    howToUse: [
      "Digite sua pergunta ou solicitação no campo de texto em linguagem natural.",
      "Use o seletor de tipo de documento para gerar rascunhos de políticas, runbooks ou relatórios.",
      "Forneça contexto adicional (ex: cole um log ou erro) para diagnósticos mais precisos.",
      "O assistente cita as fontes da Base de Conhecimento utilizadas na resposta.",
    ],
  },

  "/glpi": {
    slug: "tickets-ia",
    title: "Tickets IA",
    section: "Inteligência IA",
    status: "ga",
    description:
      "Análise inteligente de tickets de suporte integrada com o GLPI. Categoriza tickets automaticamente, identifica tickets relacionados, sugere soluções com base em histórico e gera resumos executivos de incidentes.",
    howToUse: [
      "Configure a integração com o GLPI em Configurações > Integrações.",
      "Após sincronização, os tickets são exibidos com classificação automática de categoria e prioridade.",
      "Clique em um ticket para ver a análise IA com causas prováveis e soluções sugeridas.",
      "Use 'Gerar Relatório de Incidente' para produzir um resumo formatado do ticket.",
    ],
  },

  // ── Plataforma ─────────────────────────────────────────────────────────────────
  "/audit": {
    slug: "auditoria",
    title: "Auditoria",
    section: "Plataforma",
    status: "ga",
    description:
      "Trilha de auditoria imutável de todas as ações executadas na plataforma. Registra quem fez o quê, quando e em qual dispositivo. Também centraliza operações em lote, logs de execução e jobs agendados.",
    howToUse: [
      "Use os filtros de data, usuário e tipo de ação para localizar eventos específicos.",
      "Clique em um registro para ver o contexto completo da operação (antes/depois).",
      "Na aba 'Jobs em Lote', acompanhe o progresso de operações em massa ainda em execução.",
      "Exporte registros de auditoria para evidenciar ações em processos de compliance.",
    ],
    tip: "Os registros de auditoria usam hash encadeado — qualquer tentativa de adulteração é detectada automaticamente.",
  },

  "/security-infra": {
    slug: "seguranca-da-plataforma",
    title: "Segurança da Plataforma",
    section: "Plataforma",
    status: "beta",
    description:
      "Módulo de governança de segurança da própria plataforma. Gerencia configurações de HashiCorp Vault (gestão de secrets), políticas OPA (controle de acesso baseado em código), perfis de hardening e rastreamento de pentests.",
    howToUse: [
      "Na aba 'Vault', registre instâncias do HashiCorp Vault para centralizar o gerenciamento de segredos.",
      "Na aba 'Políticas OPA', crie e teste políticas de controle de acesso em linguagem Rego.",
      "Na aba 'Perfis de Hardening', documente e rastreie a aplicação de perfis de segurança.",
      "Na aba 'Pentest Tracker', agende pentests e registre os achados após conclusão.",
    ],
    tip: "Atenção: a integração real com Vault (busca de secrets) e a aplicação de hardening em dispositivos estão em desenvolvimento. O módulo atual serve como camada de configuração e rastreamento.",
  },

  "/settings": {
    slug: "configuracoes",
    title: "Configurações",
    section: "Plataforma",
    status: "ga",
    description:
      "Central de configurações gerais da plataforma. Gerencia integrações com sistemas externos (SIEM, GLPI, Jira, AD), configurações de notificação, permissões de usuários, limites de SLA e parâmetros globais da plataforma.",
    howToUse: [
      "Na aba 'Integrações', configure conexões com sistemas externos usando as credenciais de API.",
      "Na aba 'Usuários', gerencie convites, funções e permissões dos membros da equipe.",
      "Na aba 'Notificações', defina canais (e-mail, Slack) e regras de disparo.",
      "Na aba 'SLA', configure os limites de tempo de resposta por severidade de alerta.",
    ],
  },

  "/product": {
    slug: "produto-billing",
    title: "Produto & Billing",
    section: "Plataforma",
    status: "beta",
    description:
      "Gerencia o plano de assinatura, limites de uso, faturamento e faturas da plataforma. Exibe o consumo atual de ativos monitorados, usuários ativos e armazenamento utilizado.",
    howToUse: [
      "Verifique o consumo atual em relação aos limites do plano contratado.",
      "Baixe faturas anteriores na seção de histórico de pagamentos.",
      "Solicite upgrade de plano diretamente pelo painel de billing.",
      "Receba alertas automáticos quando o uso se aproximar do limite do plano.",
    ],
  },

  "/organization": {
    slug: "organizacao",
    title: "Organização",
    section: "Plataforma",
    status: "ga",
    description:
      "Gerencia a estrutura organizacional da conta: convites de usuários, funções (admin, analista, visualizador), tenants e configurações globais da organização.",
    howToUse: [
      "Convide novos membros pelo e-mail com a função adequada.",
      "Edite as permissões de usuários existentes conforme mudanças de responsabilidade.",
      "Super admins podem gerenciar múltiplos tenants (clientes) pelo painel MSSP.",
    ],
  },

  "/mssp": {
    slug: "painel-mssp",
    title: "Painel MSSP",
    section: "Plataforma",
    status: "ga",
    description:
      "Visão consolidada de todos os clientes (tenants) gerenciados. Permite alternar entre contas, monitorar a saúde de cada cliente, identificar alertas críticos em toda a base e gerenciar usuários multi-tenant.",
    howToUse: [
      "Selecione um cliente no painel para alternar o contexto para aquela conta.",
      "Monitore o status de saúde de todos os clientes na visão consolidada.",
      "Identifique clientes com alertas críticos abertos sem resolução.",
    ],
    tip: "Disponível apenas para usuários com perfil Super Admin.",
  },
};

// Lista plana de todos os módulos para a Central de Ajuda
export const allModules: ModuleHelp[] = Object.values(helpByRoute);

// Seções na ordem de exibição da sidebar
export const sectionOrder = [
  "Início",
  "Firewalls",
  "Automação",
  "Redes & Conectividade",
  "Infraestrutura",
  "Identidade & Acesso",
  "Segurança & Resposta",
  "Conformidade",
  "Inteligência IA",
  "Plataforma",
];
