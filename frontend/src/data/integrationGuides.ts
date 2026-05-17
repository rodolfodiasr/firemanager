import type { ModuleStatus } from "./helpContent";

export interface IntegrationGuide {
  slug: string;
  title: string;
  category: IntegrationCategory;
  status: ModuleStatus;
  description: string;
  configLocation: string;
  prerequisites: string[];
  credentialSteps: string[];
  configSteps: string[];
  testStep: string;
  provides: string[];
  tip?: string;
}

export type IntegrationCategory =
  | "Monitoramento & Inteligência"
  | "Tickets & ITSM"
  | "Notificações"
  | "Identidade & Diretório"
  | "SIEM"
  | "RMM"
  | "Cloud"
  | "Infraestrutura de Segurança"
  | "Edge & SSO";

export const integrationCategoryOrder: IntegrationCategory[] = [
  "Monitoramento & Inteligência",
  "Tickets & ITSM",
  "Notificações",
  "Identidade & Diretório",
  "SIEM",
  "RMM",
  "Cloud",
  "Infraestrutura de Segurança",
  "Edge & SSO",
];

export const integrationGuides: IntegrationGuide[] = [

  // ── Monitoramento & Inteligência ─────────────────────────────────────────────

  {
    slug: "zabbix",
    title: "Zabbix",
    category: "Monitoramento & Inteligência",
    status: "ga",
    description:
      "Integra o Zabbix ao FireManager para enriquecer análises de servidores, chamados GLPI e alertas com métricas reais de hosts, triggers disparadas e dados de disponibilidade.",
    configLocation: "Organização → Integrações → Zabbix",
    prerequisites: [
      "Zabbix Server versão 6.0 ou superior (suporta v6 e v7).",
      "Usuário de API criado no Zabbix com permissão de leitura nos hosts desejados.",
      "URL de acesso ao Zabbix acessível a partir do servidor FireManager (porta 443 ou 80).",
    ],
    credentialSteps: [
      "No Zabbix, acesse Administração → Usuários → Criar usuário.",
      "Defina nome, senha e tipo de usuário como 'Super Admin' ou crie um perfil de permissão de leitura.",
      "Acesse Administração → API Tokens (Zabbix 6.0+) → Criar token.",
      "Selecione o usuário criado, defina validade (ou 'sem validade') e clique em Adicionar.",
      "Copie o token gerado — ele só é exibido uma vez.",
      "Para Zabbix 5.x (não recomendado): use autenticação por usuário+senha diretamente na API.",
    ],
    configSteps: [
      "Acesse Organização → Integrações → seção Zabbix.",
      "Preencha URL (ex: https://zabbix.empresa.com) sem barra final.",
      "Cole o API Token gerado no campo correspondente.",
      "Clique em 'Testar Conexão' para validar.",
      "Salve a configuração.",
    ],
    testStep: "Clique em 'Testar Conexão' — a resposta deve indicar a versão do Zabbix e o número de hosts visíveis ao usuário da API.",
    provides: [
      "Métricas de CPU, memória, disco e rede de servidores monitorados.",
      "Triggers disparadas (alertas ativos) por host.",
      "Correlação automática de hosts Zabbix com dispositivos e servidores do FireManager.",
      "Enriquecimento de análises de chamados GLPI com dados de monitoramento do servidor afetado.",
    ],
    tip: "O FireManager suporta Zabbix v6 (token no body) e v7 (Bearer token). A versão é detectada automaticamente — não é necessário configurar.",
  },

  {
    slug: "wazuh-monitoramento",
    title: "Wazuh",
    category: "Monitoramento & Inteligência",
    status: "ga",
    description:
      "Integra o Wazuh como fonte de alertas de segurança e vulnerabilidades. Os dados do Wazuh enriquecem análises de chamados, relatórios de postura e diagnósticos de servidores.",
    configLocation: "Organização → Integrações → Wazuh",
    prerequisites: [
      "Wazuh Manager com API REST habilitada (porta 55000 por padrão).",
      "Usuário de API Wazuh com permissão de leitura (GET) nos endpoints de agentes, alertas e vulnerabilidades.",
      "Certificado SSL válido ou configuração para aceitar self-signed.",
    ],
    credentialSteps: [
      "Acesse o Wazuh Manager via CLI: ssh user@wazuh-manager.",
      "Execute: /var/ossec/bin/wazuh-control status para confirmar que a API está rodando.",
      "Crie um usuário API: curl -u admin:admin -k -X POST https://wazuh-manager:55000/security/users -H 'Content-Type: application/json' -d '{\"username\": \"firemanager\", \"password\": \"SenhaSegura123!\"}'",
      "Anote a resposta com o ID do usuário criado.",
      "Atribua permissões: curl -u admin:admin -k -X POST https://wazuh-manager:55000/security/roles/1/users -d '{\"user_ids\": [ID_DO_USUARIO]}'",
      "A URL base da API é https://wazuh-manager:55000.",
    ],
    configSteps: [
      "Acesse Organização → Integrações → seção Wazuh.",
      "Preencha URL (ex: https://wazuh.empresa.com:55000).",
      "Informe o usuário e senha criados.",
      "Opcionalmente marque 'Ignorar verificação SSL' se usar certificado self-signed.",
      "Clique em 'Testar Conexão' e salve.",
    ],
    testStep: "O teste retorna a versão do Wazuh e o número de agentes conectados. Se retornar 'connection refused', verifique se a porta 55000 está acessível.",
    provides: [
      "Alertas de segurança por agente (HIDS events).",
      "Inventário de vulnerabilidades detectadas por agente.",
      "Status de conectividade de agentes (ativo/desconectado).",
      "Enriquecimento de chamados GLPI com alertas do agente no servidor afetado.",
    ],
  },

  {
    slug: "shodan",
    title: "Shodan",
    category: "Monitoramento & Inteligência",
    status: "ga",
    description:
      "Integra o Shodan para obter informações de reconhecimento externo sobre IPs e domínios gerenciados — portas abertas, serviços expostos e registros de banners.",
    configLocation: "Organização → Integrações → Shodan",
    prerequisites: [
      "Conta Shodan ativa (plano gratuito tem limite; plano pago recomendado para uso em produção).",
    ],
    credentialSteps: [
      "Acesse shodan.io e faça login.",
      "Clique no seu nome de usuário → My Account.",
      "Copie a API Key exibida na seção 'Overview'.",
    ],
    configSteps: [
      "Acesse Organização → Integrações → seção Shodan.",
      "Cole a API Key no campo correspondente.",
      "Salve a configuração.",
    ],
    testStep: "O teste faz uma consulta simples de informações da conta Shodan e retorna o número de créditos disponíveis.",
    provides: [
      "Portas abertas e serviços expostos por IP gerenciado.",
      "Banners de serviços (versão de software detectada externamente).",
      "Histórico de exposição e mudanças detectadas pelo Shodan.",
      "Contexto de reconhecimento para análises de segurança.",
    ],
  },

  {
    slug: "openvas",
    title: "OpenVAS / Greenbone",
    category: "Monitoramento & Inteligência",
    status: "ga",
    description:
      "Integra o OpenVAS (Greenbone Vulnerability Manager) para consumir resultados de varreduras de vulnerabilidades e correlacionar com dispositivos gerenciados.",
    configLocation: "Organização → Integrações → OpenVAS",
    prerequisites: [
      "OpenVAS ou Greenbone Community Edition instalado e com a GVM API acessível (porta 9390 por padrão).",
      "Usuário administrador do GVM.",
    ],
    credentialSteps: [
      "Acesse a interface web do Greenbone (https://openvas.empresa.com).",
      "Vá em Administration → Users → New User.",
      "Crie um usuário dedicado para a API com papel 'Admin'.",
      "Anote o usuário e senha — a autenticação é Basic Auth via GMP XML.",
    ],
    configSteps: [
      "Acesse Organização → Integrações → seção OpenVAS.",
      "Preencha a URL base (ex: https://openvas.empresa.com:9390).",
      "Informe usuário e senha do GVM.",
      "Salve e teste a conexão.",
    ],
    testStep: "O teste lista as últimas tarefas de scan disponíveis. Se a lista estiver vazia, verifique as permissões do usuário.",
    provides: [
      "CVEs detectadas por host, com CVSS score.",
      "Resultados de scans com severidade (Critical, High, Medium, Low).",
      "Enriquecimento de postura de segurança dos ativos gerenciados.",
    ],
  },

  {
    slug: "nmap",
    title: "Nmap",
    category: "Monitoramento & Inteligência",
    status: "ga",
    description:
      "Executa varreduras de descoberta de rede localmente no servidor FireManager. Não requer credenciais externas — apenas o binário nmap instalado.",
    configLocation: "Organização → Integrações → Nmap",
    prerequisites: [
      "Nmap instalado no servidor FireManager (ou dentro do container da API).",
      "O servidor FireManager deve ter conectividade de rede com os hosts a varrer.",
      "Permissão de execução de raw sockets (geralmente requer root ou capabilities net_raw).",
    ],
    credentialSteps: [
      "No servidor Linux: sudo apt install nmap (Debian/Ubuntu) ou sudo yum install nmap (RHEL/CentOS).",
      "Verifique: which nmap → anote o caminho (geralmente /usr/bin/nmap).",
      "Dentro do container Docker: docker exec api which nmap.",
    ],
    configSteps: [
      "Acesse Organização → Integrações → seção Nmap.",
      "Preencha o caminho do binário (ex: /usr/bin/nmap).",
      "Salve a configuração.",
    ],
    testStep: "Acesse Topologia & Rotas → Descobrir Rede para executar a primeira varredura.",
    provides: [
      "Descoberta automática de hosts e serviços na rede.",
      "Portas abertas e versões de serviços por host.",
      "Alimentação do mapa de topologia de rede.",
    ],
  },

  {
    slug: "bookstack",
    title: "BookStack",
    category: "Monitoramento & Inteligência",
    status: "ga",
    description:
      "Integra o BookStack como repositório de documentação técnica. Os documentos publicados são indexados com pgvector e injetados automaticamente no Assistente IA como contexto RAG.",
    configLocation: "Organização → Integrações → BookStack",
    prerequisites: [
      "Instância BookStack acessível pela rede do servidor FireManager.",
      "Conta BookStack com permissão de leitura nos livros/prateleiras desejados.",
    ],
    credentialSteps: [
      "No BookStack, acesse seu perfil (canto superior direito) → Edit Profile.",
      "Role até a seção 'API Tokens' e clique em 'Create Token'.",
      "Dê um nome (ex: firemanager-api) e defina expiração ou deixe sem validade.",
      "Copie o Token ID e Token Secret gerados — serão exibidos apenas uma vez.",
      "A autenticação é via header: Authorization: Token {token_id}:{token_secret}.",
    ],
    configSteps: [
      "Acesse Organização → Integrações → seção BookStack.",
      "Preencha a URL base (ex: https://docs.empresa.com).",
      "Cole o token no formato token_id:token_secret.",
      "Defina o Book ID padrão (visível na URL da prateleira: /books/{ID}).",
      "Opcionalmente defina o Shelf ID para filtrar a busca.",
      "Salve e aguarde a indexação inicial (pode levar alguns minutos).",
    ],
    testStep: "Acesse Base de Conhecimento e verifique se os documentos do BookStack aparecem na busca semântica.",
    provides: [
      "Documentos indexados como contexto RAG para o Assistente IA.",
      "Busca semântica no conteúdo dos livros do BookStack.",
      "Publicação automática de rascunhos gerados pelo Assistente IA.",
    ],
    tip: "Após adicionar novos livros no BookStack, acesse Base de Conhecimento → Re-indexar para atualizar o índice RAG.",
  },

  // ── Tickets & ITSM ──────────────────────────────────────────────────────────

  {
    slug: "glpi",
    title: "GLPI",
    category: "Tickets & ITSM",
    status: "ga",
    description:
      "Integra o GLPI para análise automática de chamados com IA. O FireManager consome os chamados abertos, enriquece com dados de Zabbix/Wazuh/device logs e gera diagnóstico, causa raiz e plano de ação via Claude.",
    configLocation: "Tickets IA (menu lateral) → aba Configuração",
    prerequisites: [
      "GLPI versão 10.x ou 11.x com a API REST habilitada.",
      "Usuário de API criado no GLPI com perfil que permite leitura de chamados.",
    ],
    credentialSteps: [
      "No GLPI, acesse Configuração → Geral → API.",
      "Habilite 'Habilitar API Rest' e 'Habilitar login com credenciais'.",
      "Crie um App Token: clique em 'Adicionar token de aplicativo', defina um nome (ex: firemanager) e salve — copie o token gerado.",
      "Crie um User Token: vá em Administração → Usuários → selecione o usuário de API → aba 'Chaves de API remotas' → Adicionar chave. Copie o token.",
      "Alternativamente, use usuário+senha para autenticação (menos seguro).",
      "Anote a URL base do GLPI (ex: https://glpi.empresa.com).",
    ],
    configSteps: [
      "No FireManager, acesse Tickets IA → aba Configuração.",
      "Preencha a URL do GLPI (ex: https://glpi.empresa.com).",
      "Cole o App Token e o User Token (ou usuário+senha).",
      "Configure os filtros: prioridade mínima (1-5), tipos de item (Ticket, Problem, Change), janela de análise em horas.",
      "Habilite os enriquecimentos desejados: Zabbix, Wazuh, Device Logs.",
      "Clique em 'Testar Conexão' e depois em 'Salvar'.",
      "Ative 'Análise automática' para que novos chamados sejam analisados automaticamente a cada ciclo.",
    ],
    testStep: "Clique em 'Executar Análise Agora' — o sistema busca os chamados abertos do último período configurado e exibe as análises na aba principal.",
    provides: [
      "Diagnóstico automático com causa raiz e plano de ação para cada chamado.",
      "Correlação automática de chamados com dispositivos gerenciados pelo IP/hostname do título.",
      "Enriquecimento com métricas Zabbix, alertas Wazuh e logs SSH do device correlacionado.",
      "Resposta automática no GLPI como nota de acompanhamento com o resultado da análise.",
      "Bridge para o Assistente IA: abre sessão contextualizada com o chamado para investigação aprofundada.",
    ],
    tip: "Para que a correlação automática funcione bem, inclua o IP ou hostname do servidor afetado no título ou descrição do chamado.",
  },

  {
    slug: "jira",
    title: "Jira",
    category: "Tickets & ITSM",
    status: "ga",
    description:
      "Cria tickets no Jira automaticamente quando alertas são disparados ou playbooks SOAR executam a ação 'create_ticket_jira'. Também usado para rastrear remediações.",
    configLocation: "Alertas & SIEM → aba Canais → Novo Canal → tipo Jira",
    prerequisites: [
      "Conta Jira Cloud ou Jira Server/Data Center.",
      "Usuário com permissão de criação de issues no projeto de destino.",
      "Para Jira Cloud: API Token (não senha).",
    ],
    credentialSteps: [
      "Para Jira Cloud: acesse id.atlassian.com → Segurança → Criar e gerenciar tokens de API.",
      "Clique em 'Criar token de API', dê um nome (ex: firemanager) e copie o token.",
      "Para Jira Server: use usuário+senha ou Personal Access Token (Jira 8.14+).",
      "Anote a URL base (ex: https://empresa.atlassian.net para Cloud).",
      "Anote a chave do projeto de destino (ex: INFRA, SEC — visível na URL do projeto).",
    ],
    configSteps: [
      "Acesse Alertas & SIEM → aba Canais.",
      "Clique em '+ Novo Canal' e selecione tipo 'Jira'.",
      "Preencha: URL, e-mail do usuário, API Token, chave do projeto e tipo de issue (Task, Bug, Incident).",
      "Clique em 'Testar' para criar um issue de teste e confirme que apareceu no Jira.",
      "Salve e use este canal nas regras de alerta ou nos playbooks SOAR.",
    ],
    testStep: "O teste cria um issue real no Jira com título '[FireManager Test]'. Verifique se o issue apareceu no projeto configurado e delete-o manualmente.",
    provides: [
      "Criação automática de tickets a partir de alertas de segurança.",
      "Rastreabilidade de remediações com link entre o alerta no FireManager e o issue no Jira.",
      "Ação 'create_ticket_jira' disponível nos playbooks SOAR.",
    ],
  },

  // ── Notificações ─────────────────────────────────────────────────────────────

  {
    slug: "slack",
    title: "Slack",
    category: "Notificações",
    status: "ga",
    description:
      "Envia notificações de alertas, playbooks SOAR e eventos críticos para canais do Slack. Configurado como Incoming Webhook.",
    configLocation: "Alertas & SIEM → aba Canais → Novo Canal → tipo Slack",
    prerequisites: [
      "Workspace Slack com permissão para criar Incoming Webhooks.",
      "Canal de destino já criado (ex: #alertas-seguranca).",
    ],
    credentialSteps: [
      "Acesse api.slack.com/apps → Criar Nova App → From scratch.",
      "Dê um nome (ex: FireManager Alerts) e selecione o workspace.",
      "No menu lateral, clique em 'Incoming Webhooks' e ative.",
      "Clique em 'Add New Webhook to Workspace' e selecione o canal de destino.",
      "Copie a Webhook URL gerada (formato: https://hooks.slack.com/services/T.../B.../...).",
    ],
    configSteps: [
      "Acesse Alertas & SIEM → aba Canais → '+ Novo Canal' → Slack.",
      "Cole a Webhook URL no campo correspondente.",
      "Defina um nome para identificar este canal (ex: '#alertas-soc').",
      "Salve e clique em 'Testar' para enviar uma mensagem de teste.",
    ],
    testStep: "O teste envia uma mensagem de teste no canal configurado. Verifique se a mensagem apareceu no Slack.",
    provides: [
      "Notificações em tempo real de alertas por severidade.",
      "Mensagens de playbooks SOAR quando ações são executadas.",
      "Notificações de aprovação dupla pendente para operações críticas.",
    ],
  },

  {
    slug: "teams",
    title: "Microsoft Teams",
    category: "Notificações",
    status: "ga",
    description:
      "Envia notificações para canais do Microsoft Teams via Incoming Webhook ou Power Automate.",
    configLocation: "Alertas & SIEM → aba Canais → Novo Canal → tipo Teams",
    prerequisites: [
      "Permissão para configurar Incoming Webhooks no Teams (papel de proprietário do canal).",
    ],
    credentialSteps: [
      "No Teams, clique nos '...' ao lado do canal de destino → Conectores.",
      "Busque 'Incoming Webhook' e clique em Configurar.",
      "Dê um nome (ex: FireManager) e opcionalmente faça upload de um ícone.",
      "Clique em 'Criar' e copie a Webhook URL gerada.",
    ],
    configSteps: [
      "Acesse Alertas & SIEM → aba Canais → '+ Novo Canal' → Microsoft Teams.",
      "Cole a Webhook URL no campo correspondente.",
      "Salve e teste.",
    ],
    testStep: "O teste envia um card de mensagem de teste ao canal. Verifique se apareceu no Teams.",
    provides: ["Notificações de alertas em cards formatados no Teams.", "Mensagens de playbooks e eventos críticos da plataforma."],
  },

  {
    slug: "email-smtp",
    title: "E-mail (SMTP)",
    category: "Notificações",
    status: "ga",
    description:
      "Envia notificações por e-mail via servidor SMTP. Suporta TLS/STARTTLS e autenticação por usuário e senha.",
    configLocation: "Alertas & SIEM → aba Canais → Novo Canal → tipo Email",
    prerequisites: [
      "Servidor SMTP acessível (próprio, Office 365, Gmail, SendGrid, etc.).",
      "Credenciais de um usuário de envio (evite usar contas pessoais em produção).",
    ],
    credentialSteps: [
      "Para Office 365: use smtp.office365.com, porta 587, STARTTLS, e-mail e senha do usuário de envio.",
      "Para Gmail: habilite 'Acesso a apps menos seguros' ou use uma Senha de App (recomendado): Conta Google → Segurança → Senhas de app.",
      "Para SendGrid: crie uma API Key com permissão de envio em sendgrid.com → Settings → API Keys.",
    ],
    configSteps: [
      "Acesse Alertas & SIEM → aba Canais → '+ Novo Canal' → E-mail.",
      "Preencha: servidor SMTP, porta, usuário, senha, endereço de origem e destinatários.",
      "Marque 'Usar TLS' para conexões seguras (recomendado).",
      "Salve e teste.",
    ],
    testStep: "O teste envia um e-mail de teste para os destinatários configurados. Verifique a caixa de entrada (e spam).",
    provides: ["Envio de alertas e relatórios por e-mail.", "Notificações de expiração de senha para usuários AD.", "Relatórios executivos agendados mensalmente."],
  },

  {
    slug: "webhook",
    title: "Webhook Genérico",
    category: "Notificações",
    status: "ga",
    description:
      "Envia payloads HTTP para qualquer endpoint externo. Útil para integrar com sistemas customizados, n8n, Zapier, Make ou qualquer ferramenta com API REST.",
    configLocation: "Alertas & SIEM → aba Canais → Novo Canal → tipo Webhook",
    prerequisites: ["URL de endpoint acessível pelo servidor FireManager.", "Opcionalmente: cabeçalhos de autenticação (Bearer, API Key, etc.)."],
    credentialSteps: [
      "Identifique o endpoint que deve receber os eventos (ex: https://n8n.empresa.com/webhook/alertas).",
      "Se necessário, gere um token de autenticação no sistema receptor.",
      "Determine o método HTTP esperado (POST na maioria dos casos).",
    ],
    configSteps: [
      "Acesse Alertas & SIEM → aba Canais → '+ Novo Canal' → Webhook.",
      "Preencha a URL de destino.",
      "Selecione o método (GET ou POST).",
      "Adicione cabeçalhos customizados em formato JSON se necessário (ex: {\"Authorization\": \"Bearer token\"}).",
      "Salve e teste.",
    ],
    testStep: "O teste envia um POST de teste para a URL configurada. Use ferramentas como webhook.site para inspecionar o payload recebido.",
    provides: ["Integração com qualquer sistema que aceite webhooks HTTP.", "Payload JSON com detalhes do alerta, dispositivo e tenant."],
  },

  // ── Identidade & Diretório ───────────────────────────────────────────────────

  {
    slug: "azure-ad",
    title: "Azure AD / Microsoft Entra ID",
    category: "Identidade & Diretório",
    status: "ga",
    description:
      "Integra o Azure AD (Entra ID) para sincronização de usuários, grupos, licenças e roles M365. Habilita offboarding/onboarding automatizado, revisão de acesso, JIT, e análise de postura de identidade.",
    configLocation: "Identidade → aba Providers → Adicionar Azure AD",
    prerequisites: [
      "Tenant Azure AD com permissões para registrar aplicativos (papel Application Administrator).",
      "Permissões delegadas ou de aplicativo no Microsoft Graph.",
    ],
    credentialSteps: [
      "Acesse portal.azure.com → Azure Active Directory → Registros de aplicativo → Novo registro.",
      "Dê um nome (ex: FireManager), selecione 'Contas somente neste diretório organizacional' e clique em Registrar.",
      "Copie o Application (client) ID e o Directory (tenant) ID exibidos na página de visão geral.",
      "Acesse Certificados e segredos → Novo segredo do cliente → defina validade e crie.",
      "Copie o Value do segredo gerado (só visível uma vez).",
      "Acesse Permissões de API → Adicionar uma permissão → Microsoft Graph → Permissões de aplicativo.",
      "Adicione: User.Read.All, Group.Read.All, GroupMember.ReadWrite.All (para provisionamento), Directory.Read.All, AuditLog.Read.All.",
      "Clique em 'Conceder consentimento de administrador para [organização]' e confirme.",
    ],
    configSteps: [
      "Acesse Identidade → aba Providers → '+ Adicionar Provider'.",
      "Selecione o tipo 'Azure AD'.",
      "Preencha: Tenant ID, Client ID, Client Secret.",
      "Clique em 'Testar Conexão' e depois 'Salvar'.",
      "Aguarde a sincronização inicial (Celery worker executa a cada hora).",
    ],
    testStep: "Após salvar, acesse Identidade → aba Usuários. Os usuários do Azure AD devem aparecer dentro de alguns minutos.",
    provides: [
      "Inventário de usuários, grupos, roles e licenças M365.",
      "Offboarding: revogação de acesso Azure AD, desabilitação de conta.",
      "Onboarding: adição a grupos e atribuição de licenças.",
      "Revisões de acesso, SoD e análise de postura de identidade.",
      "JIT Access via grupos do Azure AD.",
    ],
    tip: "Para ambientes com MFA P2 e Privileged Identity Management (PIM), adicione também PrivilegedAccess.Read.AzureAD às permissões.",
  },

  {
    slug: "active-directory-ldap",
    title: "Active Directory (LDAP on-premise)",
    category: "Identidade & Diretório",
    status: "ga",
    description:
      "Integra o Active Directory local via LDAP para sincronização de usuários e grupos, reset de senha, desbloqueio de conta e provisionamento de grupos no AD.",
    configLocation: "Identidade → aba Providers → Adicionar AD Local",
    prerequisites: [
      "Domain Controller acessível pelo servidor FireManager (porta 389 LDAP ou 636 LDAPS).",
      "Conta de serviço no AD com permissões de leitura na OU desejada e permissão de escrita nos grupos (para provisionamento).",
    ],
    credentialSteps: [
      "No Active Directory Users and Computers, crie um usuário de serviço (ex: svc_firemanager).",
      "Defina uma senha complexa que nunca expire.",
      "Delegue controle mínimo: direito de leitura na OU raiz (para sincronização) e 'Gerenciar membros de grupo' para as OUs onde o FireManager provisionará acesso.",
      "Anote o Bind DN completo (ex: CN=svc_firemanager,OU=ServiceAccounts,DC=empresa,DC=com).",
      "Anote o Base DN para busca de usuários (ex: DC=empresa,DC=com).",
      "Para LDAPS: exporte o certificado da CA do AD e confie no servidor FireManager.",
    ],
    configSteps: [
      "Acesse Identidade → aba Providers → '+ Adicionar Provider' → AD Local.",
      "Preencha: URL LDAP (ex: ldap://dc01.empresa.com:389 ou ldaps://dc01.empresa.com:636).",
      "Preencha Bind DN e Bind Password.",
      "Preencha Base DN para busca de usuários e grupos.",
      "Opcionalmente adicione filtros LDAP customizados (ex: (objectClass=person)).",
      "Teste a conexão e salve.",
    ],
    testStep: "O teste retorna o número de usuários encontrados no Base DN. Se retornar 0, verifique o Base DN e as permissões do Bind DN.",
    provides: [
      "Sincronização de usuários, grupos e membros do AD local.",
      "Reset de senha de usuários via LDAP Modify.",
      "Desbloqueio de contas (clear lockout).",
      "Adição/remoção de usuários em grupos para provisionamento de acesso.",
    ],
  },

  {
    slug: "google-workspace",
    title: "Google Workspace",
    category: "Identidade & Diretório",
    status: "ga",
    description:
      "Integra o Google Workspace para sincronização de usuários e grupos, gestão de ciclo de vida (offboarding/onboarding) e revisão de acesso.",
    configLocation: "Identidade → aba Providers → Adicionar Google Workspace",
    prerequisites: [
      "Conta Google Workspace com acesso de Super Admin.",
      "Google Cloud Project para criar a Service Account.",
    ],
    credentialSteps: [
      "Acesse console.cloud.google.com → IAM → Service Accounts → Criar Service Account.",
      "Dê um nome (ex: firemanager-sa), clique em Criar.",
      "Na aba 'Chaves', clique em 'Adicionar Chave → JSON' e faça download do arquivo JSON.",
      "No Google Admin (admin.google.com), acesse Segurança → Controles de API → Gerenciar acesso de apps de terceiros.",
      "Adicione o Client ID da Service Account e conceda escopos: https://www.googleapis.com/auth/admin.directory.user.readonly, https://www.googleapis.com/auth/admin.directory.group.",
      "Ative a delegação em todo o domínio (Domain-Wide Delegation) na Service Account.",
      "Anote o e-mail de um Super Admin para impersonação (admin_email).",
    ],
    configSteps: [
      "Acesse Identidade → aba Providers → '+ Adicionar Provider' → Google Workspace.",
      "Faça upload do arquivo JSON da Service Account.",
      "Preencha o Admin Email para impersonação.",
      "Teste e salve.",
    ],
    testStep: "O teste lista os primeiros 10 usuários do domínio. Verifique se retorna usuários ativos.",
    provides: [
      "Sincronização de usuários e grupos do Google Workspace.",
      "Suspensão e reativação de contas (offboarding/onboarding).",
      "Remoção de membros de grupos.",
    ],
  },

  // ── SIEM ────────────────────────────────────────────────────────────────────

  {
    slug: "wazuh-siem",
    title: "Wazuh (SIEM)",
    category: "SIEM",
    status: "ga",
    description:
      "Recebe alertas do Wazuh em tempo real via webhook. Alertas são normalizados, correlacionados com dispositivos gerenciados e podem disparar playbooks SOAR automaticamente.",
    configLocation: "Alertas & SIEM → aba SIEM → Novo Conector → tipo Wazuh",
    prerequisites: [
      "Wazuh Manager com suporte a integração de webhook (ossec-integratord).",
      "Acesso de edição aos arquivos de configuração do Wazuh Manager.",
    ],
    credentialSteps: [
      "No FireManager, após criar o conector, copie a Webhook URL gerada (formato: https://firemanager.empresa.com/webhooks/siem/{secret}).",
      "No Wazuh Manager, edite /var/ossec/etc/ossec.conf e adicione dentro de <ossec_config>:",
      "<integration><name>custom-webhook</name><hook_url>URL_DO_FIREMANAGER</hook_url><level>7</level><alert_format>json</alert_format></integration>",
      "Reinicie o Wazuh Manager: sudo systemctl restart wazuh-manager.",
    ],
    configSteps: [
      "Acesse Alertas & SIEM → aba SIEM → '+ Novo Conector'.",
      "Selecione tipo 'Wazuh'.",
      "Preencha a URL base da API Wazuh (para correlação) e o segredo do webhook.",
      "Salve — a Webhook URL é gerada automaticamente.",
      "Configure o Wazuh Manager para enviar alertas para esta URL.",
    ],
    testStep: "Após configurar o Wazuh Manager, force um alerta (ex: tente login SSH com senha errada). O alerta deve aparecer na aba SIEM em até 1 minuto.",
    provides: [
      "Alertas de segurança em tempo real normalizados no schema comum.",
      "Correlação automática com dispositivos gerenciados pelo IP de origem.",
      "Gatilho para playbooks SOAR com trigger_type: siem_alert.",
    ],
  },

  {
    slug: "microsoft-sentinel",
    title: "Microsoft Sentinel",
    category: "SIEM",
    status: "ga",
    description:
      "Recebe alertas do Microsoft Sentinel via Logic Apps webhook. Correlaciona incidentes com ativos gerenciados e pode acionar playbooks SOAR.",
    configLocation: "Alertas & SIEM → aba SIEM → Novo Conector → tipo Sentinel",
    prerequisites: [
      "Microsoft Sentinel habilitado em um workspace Log Analytics.",
      "Permissão para criar Logic Apps no Azure.",
    ],
    credentialSteps: [
      "No FireManager, crie o conector Sentinel e copie a Webhook URL gerada.",
      "No portal Azure, acesse Sentinel → Automation → Criar Playbook (Logic App).",
      "Configure o trigger: 'Quando um alerta do Microsoft Sentinel for criado'.",
      "Adicione uma ação HTTP POST para a Webhook URL do FireManager.",
      "No body da requisição, mapeie: @{triggerBody()?['properties']?['alertDisplayName']} e outros campos relevantes.",
      "Salve e ative o playbook no Sentinel.",
    ],
    configSteps: [
      "Acesse Alertas & SIEM → aba SIEM → '+ Novo Conector' → Microsoft Sentinel.",
      "Preencha o Workspace ID e a Workspace Key (para autenticação do webhook).",
      "Salve e copie a Webhook URL.",
      "Configure o Logic App no Azure conforme as etapas acima.",
    ],
    testStep: "Crie um alerta de teste no Sentinel ou aguarde um incidente real. Verifique se aparece na aba SIEM do FireManager.",
    provides: [
      "Incidentes do Sentinel normalizados e correlacionados.",
      "Acionamento de playbooks SOAR a partir de incidentes do Sentinel.",
    ],
  },

  {
    slug: "splunk",
    title: "Splunk",
    category: "SIEM",
    status: "ga",
    description:
      "Recebe alertas do Splunk via HEC (HTTP Event Collector) ou webhook de alerta. Integra eventos com a central de alertas e playbooks SOAR.",
    configLocation: "Alertas & SIEM → aba SIEM → Novo Conector → tipo Splunk",
    prerequisites: [
      "Splunk Enterprise ou Cloud com HEC habilitado.",
      "Permissão para criar Alert Actions no Splunk.",
    ],
    credentialSteps: [
      "No Splunk, acesse Settings → Data Inputs → HTTP Event Collector → New Token.",
      "Crie um token para o FireManager, anote o HEC Token e a URL (formato: https://splunk:8088).",
      "Para alertas de busca: configure uma Alert Action do tipo Webhook na busca de alerta do Splunk.",
      "Use a Webhook URL gerada no conector FireManager como destino do Alert Action.",
    ],
    configSteps: [
      "Acesse Alertas & SIEM → aba SIEM → '+ Novo Conector' → Splunk.",
      "Preencha a URL base e o HEC Token.",
      "Salve e copie a Webhook URL para usar nas Alert Actions do Splunk.",
    ],
    testStep: "Dispare manualmente uma busca com alerta configurado no Splunk e verifique se o evento aparece na aba SIEM.",
    provides: [
      "Alertas de busca do Splunk normalizados.",
      "Integração bidirecional: FireManager pode fechar/comentar alertas no Splunk após ação.",
    ],
  },

  {
    slug: "elastic-siem",
    title: "Elastic SIEM",
    category: "SIEM",
    status: "ga",
    description:
      "Integra o Elastic Security (SIEM) via API de detecção. Consome alerts gerados por regras de detecção do Elastic e correlaciona com ativos gerenciados.",
    configLocation: "Alertas & SIEM → aba SIEM → Novo Conector → tipo Elastic",
    prerequisites: [
      "Elastic Stack 7.10+ com Elastic Security habilitado.",
      "API Key com permissão de leitura nas regras de detecção.",
    ],
    credentialSteps: [
      "No Kibana, acesse Stack Management → API Keys → Create API Key.",
      "Dê um nome (ex: firemanager) e defina os privilégios: indices: [{names: ['.alerts-security*'], privileges: ['read']}].",
      "Copie a API Key gerada (formato id:key, encode em base64 para o header).",
      "Anote a URL do Kibana (ex: https://kibana.empresa.com).",
    ],
    configSteps: [
      "Acesse Alertas & SIEM → aba SIEM → '+ Novo Conector' → Elastic SIEM.",
      "Preencha a URL base do Kibana e a API Key.",
      "Salve.",
    ],
    testStep: "O conector consulta os últimos alertas de detecção. Se retornar 0, verifique se há regras de detecção ativas com alertas gerados.",
    provides: [
      "Alertas de regras de detecção do Elastic SIEM normalizados.",
      "Correlação com dispositivos pelo IP de origem do alerta.",
    ],
  },

  {
    slug: "log360",
    title: "Log360 (ManageEngine)",
    category: "SIEM",
    status: "ga",
    description:
      "Recebe alertas do Log360 da ManageEngine via webhook. Normaliza eventos de segurança e correlaciona com a infraestrutura gerenciada.",
    configLocation: "Alertas & SIEM → aba SIEM → Novo Conector → tipo Log360",
    prerequisites: [
      "Log360 com suporte a integrações de webhook habilitado.",
      "Perfil de alerta configurado no Log360.",
    ],
    credentialSteps: [
      "No Log360, acesse Configuration → Notification Profile → Add.",
      "Configure o perfil com os alertas desejados e selecione 'Webhook' como método de notificação.",
      "Use a Webhook URL do conector FireManager como destino.",
    ],
    configSteps: [
      "Acesse Alertas & SIEM → aba SIEM → '+ Novo Conector' → Log360.",
      "Preencha a URL base e a API Key do Log360.",
      "Salve e copie a Webhook URL para o perfil de notificação no Log360.",
    ],
    testStep: "Dispare um alerta de teste no Log360 e verifique se aparece na aba SIEM do FireManager.",
    provides: [
      "Alertas de segurança do Log360 normalizados.",
      "Eventos de AD, Exchange, SQL Server e dispositivos de rede monitorados pelo Log360.",
    ],
  },

  {
    slug: "qradar",
    title: "IBM QRadar",
    category: "SIEM",
    status: "ga",
    description:
      "Integra o IBM QRadar para consumir offenses e correlacionar com ativos gerenciados. Suporta autenticação via API Token.",
    configLocation: "Alertas & SIEM → aba SIEM → Novo Conector → tipo QRadar",
    prerequisites: [
      "QRadar 7.4+ com API REST habilitada.",
      "Usuário QRadar com papel 'Admin' ou criação de Security Token.",
    ],
    credentialSteps: [
      "No QRadar Console, acesse Admin → Authorized Service Tokens → Add Token.",
      "Dê permissão de leitura em 'SIEM' e 'Assets'.",
      "Copie o token gerado.",
      "Anote a URL do QRadar Console (ex: https://qradar.empresa.com).",
    ],
    configSteps: [
      "Acesse Alertas & SIEM → aba SIEM → '+ Novo Conector' → QRadar.",
      "Preencha a URL base e o API Token.",
      "Salve.",
    ],
    testStep: "O conector consulta os últimos offenses. Se retornar 0, verifique se há offenses ativos no QRadar.",
    provides: [
      "Offenses do QRadar normalizados como alertas na central.",
      "Correlação de offenses com dispositivos gerenciados pelo IP de origem.",
    ],
  },

  // ── RMM ─────────────────────────────────────────────────────────────────────

  {
    slug: "tactical-rmm",
    title: "Tactical RMM",
    category: "RMM",
    status: "beta",
    description:
      "Integra o Tactical RMM para sincronizar inventário de agentes, executar scripts remotos e monitorar endpoints diretamente pela plataforma.",
    configLocation: "RMM → aba Integrações → Novo → tipo Tactical RMM",
    prerequisites: [
      "Tactical RMM instalado e acessível via HTTPS.",
      "Usuário com permissão de API (papel 'Administrator' ou superior).",
    ],
    credentialSteps: [
      "No Tactical RMM, acesse Settings → Global Settings → API Keys.",
      "Clique em 'Add API Key', dê um nome e copie a chave gerada.",
      "Anote a URL base do Tactical RMM (ex: https://rmm.empresa.com).",
    ],
    configSteps: [
      "Acesse RMM → aba Integrações → '+ Novo' → Tactical RMM.",
      "Preencha a URL base e a API Key.",
      "Opcionalmente configure filtros por site ou cliente.",
      "Salve — a sincronização inicial de agentes é executada automaticamente.",
    ],
    testStep: "Após salvar, a aba 'Devices' do RMM deve listar os agentes do Tactical RMM com status de conectividade.",
    provides: [
      "Inventário de endpoints gerenciados pelo Tactical RMM.",
      "Execução de scripts e comandos remotos via CLI.",
      "Status de saúde dos agentes em tempo real.",
    ],
  },

  {
    slug: "ninjarmm",
    title: "NinjaRMM",
    category: "RMM",
    status: "beta",
    description:
      "Integra o NinjaRMM para sincronização de dispositivos gerenciados, execução de scripts e monitoramento de endpoints.",
    configLocation: "RMM → aba Integrações → Novo → tipo NinjaRMM",
    prerequisites: [
      "Conta NinjaRMM ativa.",
      "Permissão para criar aplicativos de API OAuth2 no NinjaRMM.",
    ],
    credentialSteps: [
      "No NinjaRMM, acesse Administration → Apps & API → API → Add.",
      "Crie uma aplicação do tipo 'API Services (Machine-to-Machine)'.",
      "Defina os escopos: monitoring, management, control.",
      "Copie o Client ID e o Client Secret gerados.",
      "A URL base da API é https://app.ninjarmm.com.",
    ],
    configSteps: [
      "Acesse RMM → aba Integrações → '+ Novo' → NinjaRMM.",
      "Preencha URL, Client ID e Client Secret.",
      "Opcionalmente filtre por organização.",
      "Salve.",
    ],
    testStep: "A lista de dispositivos NinjaRMM deve aparecer na aba 'Devices' após a primeira sincronização.",
    provides: [
      "Inventário de dispositivos Windows, macOS e Linux gerenciados.",
      "Status de conectividade e saúde do agente.",
      "Execução de scripts e automações remotas.",
    ],
  },

  {
    slug: "atera",
    title: "Atera",
    category: "RMM",
    status: "beta",
    description:
      "Integra o Atera para sincronização de agentes e execução de scripts remotos nos endpoints gerenciados.",
    configLocation: "RMM → aba Integrações → Novo → tipo Atera",
    prerequisites: ["Conta Atera ativa com permissão de API."],
    credentialSteps: [
      "No Atera, acesse Admin → API → Gerar chave de API.",
      "Copie a chave gerada.",
      "A URL base da API é https://app.atera.com.",
    ],
    configSteps: [
      "Acesse RMM → aba Integrações → '+ Novo' → Atera.",
      "Preencha a API Key.",
      "Salve.",
    ],
    testStep: "Os agentes Atera devem aparecer na aba 'Devices' após a sincronização.",
    provides: ["Inventário de endpoints Atera.", "Execução de scripts e comandos remotos."],
  },

  {
    slug: "connectwise-automate",
    title: "ConnectWise Automate",
    category: "RMM",
    status: "beta",
    description:
      "Integra o ConnectWise Automate (antigo LabTech) para sincronização de computadores gerenciados e execução de scripts remotos.",
    configLocation: "RMM → aba Integrações → Novo → tipo ConnectWise",
    prerequisites: [
      "ConnectWise Automate com API REST habilitada.",
      "Usuário de API com permissão de leitura e execução de scripts.",
    ],
    credentialSteps: [
      "No ConnectWise Automate, acesse System → Configuration → Integration → REST API.",
      "Crie credenciais de API (Client ID e Client Secret) ou gere um token de autenticação.",
      "Anote a URL do servidor (ex: https://automate.empresa.com).",
    ],
    configSteps: [
      "Acesse RMM → aba Integrações → '+ Novo' → ConnectWise Automate.",
      "Preencha URL, Client ID e Client Secret.",
      "Salve.",
    ],
    testStep: "Os computadores do ConnectWise Automate devem aparecer na aba 'Devices'.",
    provides: ["Inventário de computadores gerenciados.", "Execução de scripts remotos via API ConnectWise."],
  },

  // ── Cloud ────────────────────────────────────────────────────────────────────

  {
    slug: "aws",
    title: "Amazon Web Services (AWS)",
    category: "Cloud",
    status: "ga",
    description:
      "Conecta contas AWS para auditar Security Groups como dispositivos de firewall, inventariar recursos e detectar configurações inseguras. Usa permissão mínima de leitura via IAM.",
    configLocation: "Cloud Posture → '+ Nova Conta' → tipo AWS",
    prerequisites: [
      "Conta AWS ativa.",
      "Permissão de IAM para criar usuários ou roles com políticas de leitura.",
    ],
    credentialSteps: [
      "No console AWS, acesse IAM → Usuários → Criar usuário.",
      "Dê um nome (ex: firemanager-cspm) e selecione 'Acesso programático'.",
      "Anexe a política gerenciada 'SecurityAudit' (somente leitura em recursos de segurança).",
      "Conclua a criação e copie o Access Key ID e o Secret Access Key.",
      "Para múltiplas contas (AWS Organizations): crie um IAM Role com trust policy para a conta do FireManager.",
    ],
    configSteps: [
      "Acesse Cloud Posture → '+ Nova Conta' → AWS.",
      "Preencha Access Key ID e Secret Access Key.",
      "Selecione a(s) região(ões) a auditar.",
      "Opcionalmente adicione IDs de contas de uma AWS Organization para auditoria multi-conta.",
      "Salve e execute a primeira varredura.",
    ],
    testStep: "Clique em 'Executar Varredura'. Os Security Groups devem aparecer como dispositivos e os findings de configuração incorreta na aba de resultados.",
    provides: [
      "Security Groups como dispositivos de firewall gerenciáveis.",
      "Findings de configuração insegura (porta 22/3389 aberta para 0.0.0.0/0, etc.).",
      "Inventário de instâncias EC2, RDS, buckets S3.",
      "Aderência aos checks CIS AWS Foundations Benchmark.",
    ],
  },

  {
    slug: "azure-cloud",
    title: "Microsoft Azure (NSGs)",
    category: "Cloud",
    status: "ga",
    description:
      "Conecta subscriptions Azure para auditar Network Security Groups como dispositivos de firewall, inventariar recursos e verificar postura de segurança via Azure Security Center.",
    configLocation: "Cloud Posture → '+ Nova Conta' → tipo Azure",
    prerequisites: [
      "Subscription Azure ativa.",
      "Permissão para registrar aplicativos no Azure AD (papel Application Administrator).",
    ],
    credentialSteps: [
      "Registre um app no Azure AD: Azure Active Directory → Registros de aplicativo → Novo registro.",
      "Copie Application ID e Tenant ID.",
      "Crie um segredo: Certificados e segredos → Novo segredo → copie o Value.",
      "Atribua o papel 'Security Reader' na subscription: Subscriptions → sua sub → IAM → Adicionar atribuição de função.",
    ],
    configSteps: [
      "Acesse Cloud Posture → '+ Nova Conta' → Azure.",
      "Preencha Subscription ID, Tenant ID, Client ID e Client Secret.",
      "Salve e execute a varredura.",
    ],
    testStep: "Os NSGs da subscription devem aparecer como dispositivos na aba de Cloud Posture.",
    provides: [
      "NSGs como dispositivos de firewall gerenciáveis.",
      "Findings de configuração insegura em recursos Azure.",
      "Inventário de VMs, storage accounts, databases.",
    ],
  },

  {
    slug: "gcp",
    title: "Google Cloud Platform (GCP)",
    category: "Cloud",
    status: "ga",
    description:
      "Conecta projetos GCP para auditar regras de firewall VPC como dispositivos, inventariar recursos e verificar postura de segurança via Security Command Center.",
    configLocation: "Cloud Posture → '+ Nova Conta' → tipo GCP",
    prerequisites: [
      "Projeto GCP ativo.",
      "Permissão para criar Service Accounts no projeto.",
    ],
    credentialSteps: [
      "No GCP Console, acesse IAM → Service Accounts → Criar Service Account.",
      "Dê um nome (ex: firemanager-cspm).",
      "Atribua os papéis: 'Security Reviewer' e 'Compute Network Viewer'.",
      "Gere uma chave JSON: aba 'Chaves' → Adicionar Chave → JSON → Criar.",
      "Faça download do arquivo JSON.",
    ],
    configSteps: [
      "Acesse Cloud Posture → '+ Nova Conta' → GCP.",
      "Faça upload ou cole o conteúdo do arquivo JSON da Service Account.",
      "Preencha o Project ID.",
      "Salve e execute a varredura.",
    ],
    testStep: "As regras de firewall VPC devem aparecer como dispositivos. Findings de regras abertas (target: all instances) devem ser listados.",
    provides: [
      "Regras de firewall VPC como dispositivos gerenciáveis.",
      "Findings de configuração insegura em recursos GCP.",
      "Inventário de VMs, buckets GCS, instâncias Cloud SQL.",
    ],
  },

  // ── Infraestrutura de Segurança ──────────────────────────────────────────────

  {
    slug: "hashicorp-vault",
    title: "HashiCorp Vault",
    category: "Infraestrutura de Segurança",
    status: "beta",
    description:
      "Registra instâncias do HashiCorp Vault para gerenciamento centralizado de segredos. Atualmente funciona como config store — a busca de secrets nas operações está em desenvolvimento.",
    configLocation: "Segurança da Plataforma → aba Vault → '+ Nova Configuração'",
    prerequisites: [
      "HashiCorp Vault iniciado e com o engine KV v2 habilitado.",
      "Token de acesso com permissão de leitura no mount configurado.",
    ],
    credentialSteps: [
      "No Vault, acesse o endereço web (ex: https://vault.empresa.com:8200).",
      "Para autenticação por token: crie uma policy de leitura e gere um token: vault token create -policy=firemanager-readonly.",
      "Para AppRole: vault auth enable approle → vault write auth/approle/role/firemanager token_policies=firemanager-readonly.",
      "Copie o token ou o role_id + secret_id gerados.",
    ],
    configSteps: [
      "Acesse Segurança da Plataforma → aba Vault.",
      "Clique em '+ Nova Configuração'.",
      "Preencha: nome, URL do Vault, método de autenticação (Token, AppRole ou Kubernetes), credenciais.",
      "Defina o mount padrão (ex: secret) e o namespace (para Vault Enterprise).",
      "Salve.",
    ],
    testStep: "O status 'Verificado' com badge verde indica que o Vault está acessível com as credenciais fornecidas.",
    provides: [
      "Config store centralizado de instâncias Vault por tenant.",
      "Referências de secrets (alias → caminho/chave no Vault) para uso futuro nas operações.",
    ],
    tip: "A integração real com Vault (busca automática de credenciais de dispositivos armazenadas no Vault) está planejada para F34.cont.",
  },

  {
    slug: "opa",
    title: "Open Policy Agent (OPA)",
    category: "Infraestrutura de Segurança",
    status: "beta",
    description:
      "Gerencia políticas de controle de acesso em linguagem Rego. Permite criar e testar políticas de autorização para operações da plataforma. O avaliador atual é uma simulação local — integração com sidecar OPA real está em desenvolvimento.",
    configLocation: "Segurança da Plataforma → aba Políticas OPA",
    prerequisites: [
      "Conhecimento básico da linguagem Rego (documentação em openpolicyagent.org).",
    ],
    credentialSteps: [
      "Não requer credenciais externas — políticas são gerenciadas diretamente na plataforma.",
      "Para o sidecar OPA real (futuro): OPA em container com a API REST na porta 8181.",
    ],
    configSteps: [
      "Acesse Segurança da Plataforma → aba Políticas OPA.",
      "Clique em 'Seed Políticas' para criar as 3 políticas built-in de referência.",
      "Para criar uma política customizada: clique em '+ Nova Política', defina nome, package e escreva o código Rego.",
      "Use o botão 'Avaliar' para testar a política com um JSON de entrada antes de ativar.",
    ],
    testStep: "Clique em 'Avaliar' em qualquer política e informe um JSON de entrada (ex: {\"user\": {\"role\": \"admin\"}, \"action\": \"write\"}). O resultado mostrará allowed: true ou false.",
    provides: [
      "Políticas de autorização versionadas por tenant.",
      "Avaliação de políticas com log de decisões.",
      "3 políticas built-in: allow_read_devices, require_admin_for_write, block_critical_ops_without_approval.",
    ],
  },

  // ── Edge & SSO ───────────────────────────────────────────────────────────────

  {
    slug: "edge-agent",
    title: "Edge Agent",
    category: "Edge & SSO",
    status: "beta",
    description:
      "Instala um agente leve em redes internas (filiais, ambientes CGNAT) que abre uma conexão WebSocket sainte para o FireManager. Permite gerenciar dispositivos locais sem abrir portas de entrada no firewall perimetral.",
    configLocation: "Edge Agents & SSO → aba Edge Agents → '+ Novo Agente'",
    prerequisites: [
      "Servidor Linux ou Windows na rede interna com acesso HTTPS de saída.",
      "Docker instalado (recomendado) ou Python 3.10+.",
      "O token gerado no FireManager é exibido apenas uma vez.",
    ],
    credentialSteps: [
      "No FireManager, acesse Edge Agents & SSO → '+ Novo Agente'.",
      "Defina nome, localização e os device_ids que este agente poderá gerenciar.",
      "Salve — o token é exibido uma única vez. Copie-o imediatamente.",
    ],
    configSteps: [
      "No servidor da rede interna, execute via Docker:",
      "docker run -d --name fm-edge --restart always firemanager/edge-agent:latest --token SEU_TOKEN --server wss://firemanager.io/edge-gateway",
      "Ou via pip: pip install firemanager-edge-agent && fm-edge start --token SEU_TOKEN --server wss://firemanager.io/edge-gateway",
      "O agente se conecta automaticamente e aparece como 'Online' na lista.",
    ],
    testStep: "O status do agente muda para 'Online' (badge verde) em até 30 segundos após a conexão. A última atividade é atualizada a cada heartbeat.",
    provides: [
      "Proxy de comandos para dispositivos em redes CGNAT sem IP público.",
      "Conexão segura via WebSocket TLS 1.3 sem portas inbound.",
      "Heartbeat a cada 30 segundos — dispositivo marcado como 'unreachable' se sem resposta por 3 minutos.",
    ],
    tip: "Configure os device_ids no registro do agente para limitar quais dispositivos ele pode acessar. Sem allowlist, o agente não vira proxy genérico.",
  },

  {
    slug: "sso-azure-ad",
    title: "SSO via Azure AD / Entra ID",
    category: "Edge & SSO",
    status: "beta",
    description:
      "Configura Single Sign-On com Azure AD como provedor de identidade. Usuários da organização podem acessar o FireManager com suas credenciais corporativas. Suporta JIT provisioning e mapeamento de grupos para roles.",
    configLocation: "Edge Agents & SSO → aba SSO/OIDC → Configurar",
    prerequisites: [
      "Tenant Azure AD com permissão para registrar aplicativos.",
      "URL de callback configurada no app registration: https://firemanager.empresa.com/auth/sso/callback.",
    ],
    credentialSteps: [
      "No Azure AD, registre um novo aplicativo: Azure AD → Registros de aplicativo → Novo registro.",
      "Em 'URIs de redirecionamento', adicione: https://firemanager.empresa.com/auth/sso/callback.",
      "Copie o Application (client) ID e o Directory (tenant) ID.",
      "Crie um segredo: Certificados e segredos → Novo segredo → copie o Value.",
      "A discovery URL do Azure AD é: https://login.microsoftonline.com/{TENANT_ID}/.well-known/openid-configuration.",
    ],
    configSteps: [
      "Acesse Edge Agents & SSO → aba SSO/OIDC.",
      "Selecione provedor 'Azure AD'.",
      "Preencha Client ID, Client Secret e Tenant ID.",
      "Configure o mapeamento de grupos para roles (ex: grupo 'FireManager-Admins' → role 'admin').",
      "Opcionalmente habilite 'SSO obrigatório' para bloquear login local.",
      "Salve.",
    ],
    testStep: "Acesse a página de login do FireManager — o botão 'Entrar com Azure AD' deve aparecer. Clique e autentique com uma conta do Azure AD.",
    provides: [
      "Login único com credenciais corporativas do Azure AD.",
      "JIT provisioning: usuário criado automaticamente no primeiro login.",
      "Mapeamento de grupos Azure AD para roles do FireManager.",
      "Sessão Azure AD como fator de autenticação (sem precisar de senha separada).",
    ],
  },

  {
    slug: "sso-okta",
    title: "SSO via Okta",
    category: "Edge & SSO",
    status: "beta",
    description:
      "Configura Single Sign-On com Okta como provedor de identidade OIDC.",
    configLocation: "Edge Agents & SSO → aba SSO/OIDC → Configurar",
    prerequisites: ["Organização Okta ativa.", "Permissão para criar aplicativos OIDC no Okta."],
    credentialSteps: [
      "No Okta Admin, acesse Applications → Create App Integration → OIDC → Web Application.",
      "Defina o nome (ex: FireManager) e adicione a URL de callback: https://firemanager.empresa.com/auth/sso/callback.",
      "Copie o Client ID e o Client Secret gerados.",
      "A discovery URL é: https://empresa.okta.com/.well-known/openid-configuration.",
    ],
    configSteps: [
      "Acesse Edge Agents & SSO → aba SSO/OIDC.",
      "Selecione provedor 'Okta'.",
      "Preencha Client ID, Client Secret e Discovery URL.",
      "Configure mapeamento de grupos Okta para roles.",
      "Salve.",
    ],
    testStep: "O botão 'Entrar com Okta' deve aparecer na página de login.",
    provides: ["Login único com credenciais Okta.", "JIT provisioning de usuários.", "Mapeamento de grupos Okta para roles."],
  },

  {
    slug: "sso-google",
    title: "SSO via Google",
    category: "Edge & SSO",
    status: "beta",
    description:
      "Configura Single Sign-On com Google como provedor de identidade OIDC.",
    configLocation: "Edge Agents & SSO → aba SSO/OIDC → Configurar",
    prerequisites: ["Projeto Google Cloud ativo.", "Permissão para criar OAuth 2.0 credentials."],
    credentialSteps: [
      "No Google Cloud Console, acesse APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client IDs.",
      "Tipo: Web application.",
      "Adicione o URI de redirecionamento autorizado: https://firemanager.empresa.com/auth/sso/callback.",
      "Copie o Client ID e o Client Secret.",
      "A discovery URL do Google é: https://accounts.google.com/.well-known/openid-configuration.",
    ],
    configSteps: [
      "Acesse Edge Agents & SSO → aba SSO/OIDC.",
      "Selecione provedor 'Google'.",
      "Preencha Client ID e Client Secret.",
      "Salve.",
    ],
    testStep: "O botão 'Entrar com Google' deve aparecer na página de login.",
    provides: ["Login único com conta Google corporativa.", "JIT provisioning de usuários autenticados via Google."],
  },
];

// Agrupados por categoria
export const integrationsByCategory: Record<IntegrationCategory, IntegrationGuide[]> =
  integrationGuides.reduce((acc, guide) => {
    if (!acc[guide.category]) acc[guide.category] = [];
    acc[guide.category].push(guide);
    return acc;
  }, {} as Record<IntegrationCategory, IntegrationGuide[]>);
