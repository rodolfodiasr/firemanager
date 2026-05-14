"""AI Assistant Service — RAG + LLM + audit hash-chain + pastas + compartilhamento."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, desc, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import AssistantFolder, AssistantMessage, AssistantSession
from app.models.user_tenant_role import TenantRole
from app.services.assistant_data_scope import build_context_for_query
from app.services.llm_provider import get_provider
from app.services import llm_config_service as _llm_svc

# ── Hierarquia de roles para controle de visibilidade de pastas ───────────────

_ROLE_ORDER: dict[str, int] = {
    "readonly":   0,
    "analyst_n1": 1,
    "analyst":    1,   # alias legado
    "analyst_n2": 2,
    "admin":      3,
}

def _roles_visible_to(user_role: TenantRole) -> list[str]:
    """Retorna todos os valores de min_role acessíveis para este role."""
    level = _ROLE_ORDER.get(user_role.value, 0)
    return [r for r, lv in _ROLE_ORDER.items() if lv <= level]

# ── Pastas padrão por domínio ─────────────────────────────────────────────────

_DEFAULT_TEAM_FOLDERS: list[dict] = [
    {"name": "Firewalls — Geral",        "color": "#f97316", "min_role": "analyst_n1"},
    {"name": "Firewalls — N2 Avançado",  "color": "#ef4444", "min_role": "analyst_n2"},
    {"name": "Redes — Geral",            "color": "#3b82f6", "min_role": "analyst_n1"},
    {"name": "Redes — N2 Avançado",      "color": "#6366f1", "min_role": "analyst_n2"},
    {"name": "Servidores — Geral",       "color": "#10b981", "min_role": "analyst_n1"},
    {"name": "Administração",            "color": "#8b5cf6", "min_role": "admin"},
]

_ASSISTANT_SYSTEM_TEMPLATE = """\
Você é o AI Assistant do Eternity SecOps, plataforma de operação de infraestrutura \
de segurança com IA agentic para MSSPs.

SUAS CAPACIDADES:
- Responder perguntas sobre dispositivos gerenciados, regras de firewall, compliance, \
identidade e histórico de operações do tenant
- Consultar e explicar informações da base de conhecimento e snapshots de dispositivos
- Explicar conceitos de segurança, boas práticas e como usar a plataforma
- Ajudar o analista a formular o pedido correto para o Agente Operacional (que executa ações)

RESTRIÇÕES ABSOLUTAS — não negocie:
- Não executa operações, não altera configurações, não aplica comandos
- Não revela credenciais, senhas, chaves API, tokens ou valores cifrados
- Não acessa dados de outros tenants — você só vê o contexto fornecido abaixo
- Se não encontrar a informação no contexto, diga claramente que não tem acesso

CONTEXTO DO TENANT (dados atuais):
{context}

Responda em português. Seja preciso, objetivo e seguro.\
"""

_GENERAL_SYSTEM_TEMPLATE = """\
Você é um assistente especialista em Tecnologia da Informação com amplo conhecimento em: \
redes, sistemas operacionais, infraestrutura de servidores, telefonia IP (VoIP, PABX, ramais SIP, \
softphones como Mesa Virtual Intelbras), segurança da informação, cloud, virtualização, \
suporte técnico e boas práticas de TI.

SUAS CAPACIDADES:
- Responder perguntas técnicas gerais de TI, independentemente do escopo da plataforma
- Auxiliar em troubleshooting, configuração e planejamento de infraestrutura
- Explicar conceitos técnicos, comparar tecnologias e recomendar soluções
- Ajudar a criar roteiros, checklists e procedimentos técnicos
- Suporte a telefonia: configuração de PABX IP, ramais virtuais, softphones, SIP trunk, \
QoS para VoIP, Mesa Virtual Intelbras e similares

RESTRIÇÕES ABSOLUTAS — não negocie:
- Não executa operações na infraestrutura gerenciada pela plataforma
- Não revela credenciais, senhas, chaves API ou tokens
- Não realiza ações destrutivas ou ilegais

Responda em português. Seja preciso, didático e objetivo.\
"""

_PLATFORM_GUIDE_TEMPLATE = """\
Você é o Guia da Plataforma Eternity SecOps — especialista em todos os módulos, \
funcionalidades e fluxos de trabalho da plataforma. Seu papel é explicar como usar \
a plataforma para resolver problemas específicos, indicando o caminho exato: \
menu → aba → botão → formulário.

VOCÊ NÃO EXECUTA OPERAÇÕES. Você ENSINA como usar a plataforma.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MÓDULOS E ONDE ESTÃO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▶ DISPOSITIVOS (menu: Dispositivos)
Cadastro e gerenciamento de firewalls, switches, servidores e cloud.
Vendors: Fortinet, SonicWall, pfSense, OPNsense, MikroTik, Cisco, Juniper,
HP Comware, Dell N-Series, Aruba, AWS SG, Azure NSG, GCP Firewall.
Ações: adicionar device, testar conexão, health check, grupos de dispositivos.

▶ OPERAÇÕES COM AGENTE IA (menu: Operações)
Solicitar ação ao agente em linguagem natural. O agente gera um plano com
preview dos comandos exatos antes de executar. Aprovação humana obrigatória.
- Dry-run: botão "Simular" — preview sem executar no device
- Bulk Jobs: mesma operação em múltiplos devices (menu: Bulk Jobs)
- Histórico: audit trail imutável de toda operação executada

▶ SNAPSHOTS E INSPETOR (menu: Dispositivos → Inspecionar)
Snapshot captura configuração completa (regras, NAT, rotas, interfaces).
Inspetor ao vivo: visualização em tempo real. Snapshots publicados no BookStack.

▶ MIGRAÇÃO DE REGRAS (menu: Migração)
Parser de config exportada de Fortinet/SonicWall/Sophos. Gera plano de migração
com mapeamento de objetos. Preview antes de aplicar.

▶ GOLDEN CONFIG (menu: Golden Config)
Templates com variáveis por tenant/device. Biblioteca de templates por vendor.
Bundles de implantação completa de filial (base + regras + VPN + filtro web).
Detecta divergência entre device e template. Bundles aplicam via REST ou SSH.

▶ BASE DE CONHECIMENTO IA (menu: Conhecimento)
Upload de PDF/DOCX/MD indexados via pgvector. Documentos gerados pelo AI Assistant.
Integração com BookStack. Alimenta o contexto RAG do assistente.

▶ AI ASSISTANT (botão flutuante ou menu: /assistant)
Chat em linguagem natural. Modos:
- Infraestrutura: RAG com contexto do tenant (devices, regras, compliance)
- Tecnologia Geral: especialista amplo em TI, VoIP, redes, servidores
- Guia da Plataforma: este modo — explica como usar a plataforma
Pastas de sessões (pessoais e de equipe com controle por role).
Gerar documentação: Artigo / Plano de Ação / Remediação direto da conversa.

▶ DLP — Prevenção de Perda de Dados (menu: Organização → aba DLP)
20 regras built-in: CPF, CNPJ, PIS, Título Eleitor, SSH Keys, JWT, AWS Keys,
SNMP Community, VPN PSK, TACACS+, LDAP Bind Password, BGP MD5, etc.
Regras custom via regex. Incidentes logados sem armazenar o dado original.
Compliance mode: impede desativação do DLP por admin de tenant.

▶ GLPI — INTEGRAÇÃO DE CHAMADOS (menu: GLPI)
Análise automática de chamados com Claude AI. Enriquecimento com Zabbix/Wazuh.
Bridge: abrir chamado no AI Assistant para continuar investigação em linguagem natural.
Configurar: URL + app_token + credenciais (menu: GLPI → Configurações).

▶ FIRMWARE E CVEs (menu: Firmware)
Histórico de versões de firmware por device. Correlação com banco NVD.
Status por vulnerabilidade: open / accepted / patched.

▶ GOVERNANÇA DE IDENTIDADE (menu: Identidade)
Inventário contínuo AD on-premise (ldap3) e Azure AD / M365 (Microsoft Graph).
- Campanhas de revisão de acesso: por manager / por grupo / por sistema
- SoD (Segregação de Funções): detecta conflitos de permissão perigosos
- JIT: acesso temporário com aprovação obrigatória + revogação automática
- Role mining e acessos excessivos: detecta privilege creep
- Score de postura de identidade 0–100

▶ SELF-SERVICE DE IDENTIDADE (portal dedicado)
Reset de senha e desbloqueio de conta via OTP por email.
Lembretes proativos de senha expirando (14/7/1 dias antes).
Configurar em: Organização → Identidade Self-Service.

▶ SOAR — PLAYBOOKS (menu: Playbooks)
Builder visual drag-and-drop. Templates prontos: offboarding imediato,
conta comprometida, JIT abuse, device unreachable.
Triggers: risk_score, anomalia, guardrail_block, alerta SIEM, device_unreachable.
Actions: notificar Slack/email, isolar device, criar ticket Jira, desabilitar conta AD.
Métrica MTTR disponível em: Playbooks → Estatísticas.

▶ THREAT INTELLIGENCE (menu: Playbooks → Threat Intel)
Feeds: OTX AlienVault, AbuseIPDB, CISA KEV, URLhaus, Feodo Tracker.
Correlação automática com regras dos firewalls gerenciados.

▶ SIEM — INTEGRADOR DE ALERTAS (menu: SIEM)
Conectores: Wazuh, Splunk, Microsoft Sentinel, Elastic, Log360, QRadar.
Webhook receptor de alertas. Trigger SOAR automático por alerta SIEM.
Resposta automática de volta ao SIEM após ação executada.

▶ CLOUD SECURITY — CSPM (menu: Cloud)
AWS Security Groups, Azure NSGs, GCP Firewall Rules como devices gerenciáveis.
Detecção de misconfigurations: porta 22 aberta, NSG sem logging, etc.
Checks CIS AWS/Azure/GCP integrados ao compliance.

▶ INFRAESTRUTURA DE SEGURANÇA (menu: Segurança Avançada)
- HashiCorp Vault: config store e referências a secrets
- OPA Políticas: políticas Rego com avaliação e log
- Perfis de Hardening: templates CIS/PCI aplicáveis
- Pentest Tracker: agendamento e registro de pentests

▶ EDGE AGENTS E SSO (menu: Plataforma)
Edge Agents: registro de agentes on-premise para ambientes CGNAT (sem porta inbound).
SSO/OIDC: Azure AD, Okta, Google para login federado.
Marketplace: plugins de vendor e integrações.
RBAC Granular: roles customizadas além dos 3 padrões (admin/analyst/readonly).

▶ PRODUTO E BILLING (menu: Produto)
Billing: planos Starter/Pro/Enterprise, assinatura ativa, faturas.
Onboarding: checklist guiado de 4 etapas para novos tenants.
Central de Ajuda: artigos de documentação integrados.
Preferências: idioma, timezone, tema.

▶ ORGANIZAÇÃO E ALERTAS (menu: Organização)
Gestão de usuários e convites. Configuração de alertas (Slack, Teams, Email, Webhook, Jira).
Aba DLP para prevenção de perda de dados. Branding white-label.

▶ DASHBOARD EXECUTIVO (menu: Dashboard)
Score de risco 0–100. Métricas agregadas: devices, operações, compliance score.
Relatório PDF executivo sob demanda.

▶ PAINEL MSSP — SUPER ADMIN (menu: MSSP)
Visão cross-tenant de todos os clientes. Health status global.
Support Mode: entrar em tenant específico (botão no header com banner amarelo).
Gestão de tenants, usuários e configurações globais.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGRAS DE RESPOSTA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Sempre indique o CAMINHO exato: menu → submenu → aba → botão
2. Para sequências, use listas numeradas (passo a passo)
3. Para configurações, liste os campos necessários
4. Se a funcionalidade não existir ainda, diga claramente
5. Seja direto — o usuário quer resolver um problema

Responda em português. Seja preciso, objetivo e prático.\
"""


def _compute_hash(prev_hash: str, role: str, content: str) -> str:
    data = f"{prev_hash}|{role}|{content}|{datetime.utcnow().isoformat()}"
    return hashlib.sha256(data.encode()).hexdigest()


# ── Session internals ─────────────────────────────────────────────────────────

_GLPI_CONTEXT_TEMPLATE = """\

CONTEXTO DO TICKET GLPI:
Tipo: {itemtype} | ID: #{ticket_id}
Título: {title}
{content_block}
Você está investigando este ticket. Use o contexto acima para orientar sua análise.
Quando o analista finalizar a investigação, ele poderá clicar em "Enviar para GLPI" \
para postar o resultado diretamente no ticket como followup.
"""


def _build_glpi_context(session: "AssistantSession", content: str | None = None) -> str:
    content_block = f"Descrição: {content}" if content else ""
    return _GLPI_CONTEXT_TEMPLATE.format(
        itemtype=session.glpi_itemtype or "Ticket",
        ticket_id=session.glpi_ticket_id,
        title=session.glpi_ticket_title or "",
        content_block=content_block,
    )


async def _get_or_create_session(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    session_id: UUID | None,
    model_preference: str | None,
    folder_id: UUID | None = None,
) -> AssistantSession:
    if session_id:
        result = await db.execute(
            select(AssistantSession).where(
                AssistantSession.id == session_id,
                AssistantSession.tenant_id == tenant_id,
                AssistantSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session:
            return session

    provider = await _llm_svc.resolve_provider(tenant_id, db, preference=model_preference)
    session = AssistantSession(
        tenant_id=tenant_id,
        user_id=user_id,
        model_used=provider.name,
        folder_id=folder_id,
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def _load_history(db: AsyncSession, session_id: UUID, limit: int = 20) -> list[dict]:
    result = await db.execute(
        select(AssistantMessage)
        .where(AssistantMessage.session_id == session_id)
        .order_by(AssistantMessage.created_at)
        .limit(limit)
    )
    return [{"role": m.role, "content": m.content} for m in result.scalars().all()]


# ── Send message ──────────────────────────────────────────────────────────────

async def send_message(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    user_role: TenantRole,
    session_id: UUID | None,
    content: str,
    model_preference: str | None,
    folder_id: UUID | None = None,
    mode: str = "infrastructure",
) -> tuple[AssistantSession, AssistantMessage]:
    from app.agent.guardrails import check_action_plan
    _safe_plan: dict = {
        "intent": "assistant_query",
        "ssh_commands": [],
        "raw_intent_data": {"description": content},
    }
    _gr = check_action_plan(_safe_plan, content)
    if _gr.blocked:
        raise ValueError(f"Mensagem bloqueada pela política de segurança: {_gr.block_reason}")

    session = await _get_or_create_session(
        db, tenant_id, user_id, session_id, model_preference, folder_id
    )

    prev_hash = session.last_hash or ""
    user_msg = AssistantMessage(
        session_id=session.id,
        role="user",
        content=content,
        rag_context_used=False,
        message_hash=_compute_hash(prev_hash, "user", content),
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)
    await db.flush()
    await db.refresh(user_msg)

    is_general = mode == "general"
    is_platform = mode == "platform"
    if is_general:
        system = _GENERAL_SYSTEM_TEMPLATE
        context = None
    elif is_platform:
        system = _PLATFORM_GUIDE_TEMPLATE
        context = None
    else:
        context = await build_context_for_query(db, tenant_id, user_role, content)
        base_context = context or "(nenhum contexto disponível)"
        # Append GLPI ticket context when session is linked to a ticket
        if session.glpi_ticket_id:
            glpi_ctx = _build_glpi_context(session)
            base_context = base_context + "\n" + glpi_ctx
        system = _ASSISTANT_SYSTEM_TEMPLATE.replace("{context}", base_context)

    history = await _load_history(db, session.id, limit=18)
    if not history or history[-1]["content"] != content:
        history.append({"role": "user", "content": content})

    provider = await _llm_svc.resolve_provider(tenant_id, db, preference=model_preference or session.model_used)
    response_text, input_tok, output_tok = await provider.chat(history, system)

    ai_msg = AssistantMessage(
        session_id=session.id,
        role="assistant",
        content=response_text,
        model=provider.name,
        input_tokens=input_tok,
        output_tokens=output_tok,
        rag_context_used=bool(context) if not (is_general or is_platform) else False,
        message_hash=_compute_hash(user_msg.message_hash, "assistant", response_text),
        created_at=datetime.now(timezone.utc),
    )
    db.add(ai_msg)

    session.last_hash = ai_msg.message_hash
    session.message_count += 2
    session.model_used = provider.name
    if not session.title:
        session.title = content[:80]

    await db.flush()
    await db.refresh(session)
    await db.refresh(ai_msg)
    await db.commit()

    return session, ai_msg


# ── Session queries ───────────────────────────────────────────────────────────

async def list_sessions(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    limit: int = 100,
) -> list[AssistantSession]:
    """Sessões do próprio usuário — fixadas primeiro, depois por updated_at."""
    result = await db.execute(
        select(AssistantSession)
        .where(
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id == user_id,
        )
        .order_by(
            desc(AssistantSession.pinned),
            desc(AssistantSession.updated_at),
        )
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_team_sessions(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    user_role: TenantRole,
    limit: int = 100,
) -> list[AssistantSession]:
    """Sessões visíveis para a equipe: is_shared=True ou em pasta de equipe acessível."""
    visible_roles = _roles_visible_to(user_role)
    result = await db.execute(
        select(AssistantSession)
        .outerjoin(AssistantFolder, AssistantSession.folder_id == AssistantFolder.id)
        .where(
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id != user_id,
            or_(
                AssistantSession.is_shared.is_(True),
                and_(
                    AssistantFolder.is_team.is_(True),
                    AssistantFolder.min_role.in_(visible_roles),
                ),
            ),
        )
        .order_by(desc(AssistantSession.updated_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_session_with_messages(
    db: AsyncSession,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> tuple[AssistantSession, list[AssistantMessage]] | None:
    """Retorna sessão + mensagens. Permite acesso a sessões compartilhadas."""
    result = await db.execute(
        select(AssistantSession).where(
            AssistantSession.id == session_id,
            AssistantSession.tenant_id == tenant_id,
            or_(
                AssistantSession.user_id == user_id,
                AssistantSession.is_shared.is_(True),
            ),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    msg_result = await db.execute(
        select(AssistantMessage)
        .where(AssistantMessage.session_id == session_id)
        .order_by(AssistantMessage.created_at)
    )
    return session, list(msg_result.scalars().all())


async def delete_session(
    db: AsyncSession,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> bool:
    result = await db.execute(
        select(AssistantSession).where(
            AssistantSession.id == session_id,
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return False
    await db.delete(session)
    await db.commit()
    return True


# ── Session mutations ─────────────────────────────────────────────────────────

async def rename_session(
    db: AsyncSession,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    title: str,
) -> AssistantSession | None:
    result = await db.execute(
        select(AssistantSession).where(
            AssistantSession.id == session_id,
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    session.title = title[:120]
    await db.flush()
    await db.refresh(session)
    await db.commit()
    return session


async def move_session(
    db: AsyncSession,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    folder_id: UUID | None,
) -> AssistantSession | None:
    result = await db.execute(
        select(AssistantSession).where(
            AssistantSession.id == session_id,
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    # Validar que a pasta pertence ao tenant (se informada)
    if folder_id:
        f = await db.execute(
            select(AssistantFolder).where(
                AssistantFolder.id == folder_id,
                AssistantFolder.tenant_id == tenant_id,
            )
        )
        if not f.scalar_one_or_none():
            return None
    session.folder_id = folder_id
    await db.flush()
    await db.refresh(session)
    await db.commit()
    return session


async def share_session(
    db: AsyncSession,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    shared: bool,
) -> AssistantSession | None:
    result = await db.execute(
        select(AssistantSession).where(
            AssistantSession.id == session_id,
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    session.is_shared = shared
    session.shared_by = user_id if shared else None
    await db.flush()
    await db.refresh(session)
    await db.commit()
    return session


async def pin_session(
    db: AsyncSession,
    session_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    pinned: bool,
) -> AssistantSession | None:
    result = await db.execute(
        select(AssistantSession).where(
            AssistantSession.id == session_id,
            AssistantSession.tenant_id == tenant_id,
            AssistantSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    session.pinned = pinned
    await db.flush()
    await db.refresh(session)
    await db.commit()
    return session


# ── Folder CRUD ───────────────────────────────────────────────────────────────

async def _seed_default_folders(db: AsyncSession, tenant_id: UUID) -> None:
    """Cria pastas de equipe padrão se o tenant ainda não tiver nenhuma."""
    existing = await db.execute(
        select(AssistantFolder).where(
            AssistantFolder.tenant_id == tenant_id,
            AssistantFolder.is_team.is_(True),
        ).limit(1)
    )
    if existing.scalar_one_or_none():
        return
    for spec in _DEFAULT_TEAM_FOLDERS:
        db.add(AssistantFolder(
            tenant_id=tenant_id,
            user_id=None,
            name=spec["name"],
            color=spec["color"],
            is_team=True,
            min_role=spec["min_role"],
        ))
    await db.flush()
    await db.commit()


async def list_folders(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    user_role: TenantRole,
) -> list[AssistantFolder]:
    """Pastas pessoais do usuário + pastas de equipe visíveis pelo seu role."""
    await _seed_default_folders(db, tenant_id)
    visible_roles = _roles_visible_to(user_role)
    result = await db.execute(
        select(AssistantFolder)
        .where(
            AssistantFolder.tenant_id == tenant_id,
            or_(
                AssistantFolder.user_id == user_id,
                and_(
                    AssistantFolder.is_team.is_(True),
                    AssistantFolder.min_role.in_(visible_roles),
                ),
            ),
        )
        .order_by(AssistantFolder.is_team, AssistantFolder.name)
    )
    return list(result.scalars().all())


async def create_folder(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    name: str,
    color: str,
    is_team: bool,
    min_role: str = "analyst_n1",
) -> AssistantFolder:
    folder = AssistantFolder(
        tenant_id=tenant_id,
        user_id=None if is_team else user_id,
        name=name[:80],
        color=color,
        is_team=is_team,
        min_role=min_role if is_team else "readonly",
    )
    db.add(folder)
    await db.flush()
    await db.refresh(folder)
    await db.commit()
    return folder


async def update_folder(
    db: AsyncSession,
    folder_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    name: str | None,
    color: str | None,
) -> AssistantFolder | None:
    result = await db.execute(
        select(AssistantFolder).where(
            AssistantFolder.id == folder_id,
            AssistantFolder.tenant_id == tenant_id,
            or_(
                AssistantFolder.user_id == user_id,
                AssistantFolder.is_team.is_(True),
            ),
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        return None
    if name is not None:
        folder.name = name[:80]
    if color is not None:
        folder.color = color
    await db.flush()
    await db.refresh(folder)
    await db.commit()
    return folder


async def delete_folder(
    db: AsyncSession,
    folder_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
) -> bool:
    result = await db.execute(
        select(AssistantFolder).where(
            AssistantFolder.id == folder_id,
            AssistantFolder.tenant_id == tenant_id,
            or_(
                AssistantFolder.user_id == user_id,
                AssistantFolder.is_team.is_(True),
            ),
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        return False
    # Sessões ficam com folder_id = NULL (ON DELETE SET NULL na FK)
    await db.delete(folder)
    await db.commit()
    return True
