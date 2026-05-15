"""Main AI agent orchestrator."""
import anthropic
from typing import Any
from uuid import UUID

from app.agent.context_collector import ask_clarification, get_next_question
from app.agent.intent_parser import parse_intent
from app.agent.plan_generator import generate_action_plan
from app.config import settings
from app.models.device import Device
from app.policy_engine.schemas import ActionPlan, IntentType

_ANALYSIS_SYSTEM = (
    "Você é um especialista em diagnóstico de infraestrutura de rede e segurança. "
    "Analise SOMENTE os dados coletados do dispositivo que estão no contexto da conversa. "
    "NÃO INVENTE dados, IPs, métricas ou configurações que não estejam nos dados fornecidos. "
    "Se o usuário pedir informações que não estão nos dados coletados, indique quais comandos "
    "precisariam ser executados para obter essa informação. Responda em português."
)

_REQUIRED_FIELDS_BY_INTENT: dict[str, list[str]] = {
    "create_rule": ["name", "src_address", "dst_address", "service", "action"],
    "delete_rule": ["rule_id"],
    "edit_rule": ["rule_id"],
    "create_group": ["name", "members"],
    "list_rules": [],
    "list_nat_policies": [],
    "create_nat_policy": ["name", "destination", "translated_destination"],
    "delete_nat_policy": ["rule_id"],
    "list_route_policies": [],
    "create_route_policy": ["interface", "destination", "gateway"],
    "delete_route_policy": ["rule_id"],
    "configure_content_filter": ["profile_name"],
    "health_check": [],
    "get_snapshot": [],
    "create_vlan": [],
    "delete_vlan": [],
    "configure_port": [],
    "list_vlans": [],
    "list_ports": [],
    "get_info": [],
}


class AgentSession:
    """Holds the state of an ongoing agent conversation for one operation."""

    def __init__(self, device: Device, bookstack_context: str = "", db: Any = None) -> None:
        self.device = device
        self.bookstack_context = bookstack_context
        self.db = db
        self.tenant_id: UUID | None = getattr(device, "tenant_id", None)
        self.conversation_history: list[dict[str, str]] = []
        self.intent: str | None = None
        self.collected_data: dict[str, Any] = {}
        self.missing_fields: list[str] = []
        self.plan: ActionPlan | None = None
        self.ready_to_execute: bool = False
        self.analysis_mode: bool = False
        self.executed_commands: list[str] = []
        self.executed_output: str = ""

    def inject_execution_context(
        self,
        commands: list[str],
        output: str,
        analysis: dict[str, Any] | None = None,
    ) -> None:
        """Reconstruct session state from a completed execution so the user can ask follow-up questions."""
        self.analysis_mode = True
        self.intent = "get_info"
        self.ready_to_execute = False
        self.executed_commands = commands
        self.executed_output = output

        summary_line = ""
        if analysis and analysis.get("summary"):
            summary_line = f"\nResumo da análise: {analysis['summary']}"

        data_block = (
            "═══ DADOS REAIS COLETADOS DO DISPOSITIVO ═══\n"
            f"Comandos executados: {', '.join(commands)}\n"
            f"{summary_line}\n"
            f"Saída do dispositivo:\n{output[:5000]}\n"
            "═══ FIM DOS DADOS — NÃO INVENTE INFORMAÇÕES ALÉM DESTES DADOS ═══"
        )
        self.conversation_history = [
            {"role": "user", "content": "[Sistema: dados de diagnóstico coletados do dispositivo]"},
            {"role": "assistant", "content": data_block},
        ]

    def _compute_missing(self) -> list[str]:
        required = _REQUIRED_FIELDS_BY_INTENT.get(self.intent or "unknown", [])
        return [f for f in required if f not in self.collected_data]

    async def _describe_image(self, data: str, mime_type: str, user_message: str) -> str:
        """Get a textual description of an attached image via Anthropic vision."""
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        try:
            msg = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": data}},
                        {"type": "text", "text": (
                            "Descreva o que está nesta imagem em relação a configurações de rede, firewall "
                            f"ou infraestrutura de TI. Contexto do usuário: {user_message or 'sem contexto adicional'}"
                        )},
                    ],
                }],
            )
            return msg.content[0].text if msg.content else ""
        except Exception:
            return "[Imagem anexada — não foi possível processar o conteúdo visual]"

    async def process(self, user_message: str, attachment: dict | None = None) -> str:
        """Process a user message and return the agent response."""
        # Build effective message from attachment
        effective_message = user_message
        if attachment:
            att_type = attachment.get("type", "")
            filename = attachment.get("filename", "arquivo")
            if att_type == "text":
                content = attachment.get("data", "")[:5000]
                effective_message = f"[Arquivo: {filename}]\n```\n{content}\n```\n\n{user_message}"
            elif att_type == "image":
                description = await self._describe_image(
                    attachment.get("data", ""),
                    attachment.get("mime_type", "image/jpeg"),
                    user_message,
                )
                effective_message = f"[Imagem: {filename}]\n{description}\n\n{user_message}"

        self.conversation_history.append({"role": "user", "content": effective_message})

        # Analysis mode: LLM answers from already-collected device data — no SSH, no plan generation
        if self.analysis_mode:
            response = await self._analyze_with_context(effective_message)
            self.conversation_history.append({"role": "assistant", "content": response})
            return response

        # First message: parse intent
        if self.intent is None:
            result = await parse_intent(effective_message, tenant_id=self.tenant_id, db=self.db)
            self.intent = result.intent
            self.collected_data.update(result.extracted_data)
            self.missing_fields = self._compute_missing()

            # Remap diagnose to get_info: execute read-only diagnostic commands directly
            if self.intent == "diagnose":
                self.intent = "get_info"
                self.missing_fields = []
        else:
            # Subsequent messages: extract data from user reply
            await self._extract_from_reply(effective_message)
            self.missing_fields = self._compute_missing()

        # Check if we can build the plan
        if not self.missing_fields:
            self.plan = await generate_action_plan(
                device_id=self.device.id,
                vendor=self.device.vendor.value,
                firmware_version=self.device.firmware_version,
                intent=self.intent or "unknown",
                collected_data=self.collected_data,
                bookstack_context=self.bookstack_context,
                tenant_id=self.tenant_id,
                db=self.db,
            )
            self.ready_to_execute = True
            response = self._format_plan_summary()
        else:
            response = await ask_clarification(
                self.conversation_history, self.missing_fields, self.collected_data
            )

        self.conversation_history.append({"role": "assistant", "content": response})
        return response

    async def _analyze_with_context(self, user_message: str) -> str:
        """Answer a follow-up question using only the collected device data in conversation history."""
        messages = list(self.conversation_history)

        if self.db is not None and self.tenant_id is not None:
            try:
                from app.services.llm_config_service import resolve_provider
                provider = await resolve_provider(self.tenant_id, self.db)
                response_text, _, _ = await provider.chat(
                    messages=messages,
                    system=_ANALYSIS_SYSTEM,
                    max_tokens=2048,
                )
                return response_text
            except Exception:
                pass

        # Fallback: direct Anthropic call
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        try:
            msg = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=2048,
                system=_ANALYSIS_SYSTEM,
                messages=messages,
            )
        except anthropic.InternalServerError as exc:
            if exc.status_code == 529:
                msg = await client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=2048,
                    system=_ANALYSIS_SYSTEM,
                    messages=messages,
                )
            else:
                raise
        return msg.content[0].text if msg.content else "Não foi possível analisar os dados."

    async def _extract_from_reply(self, reply: str) -> None:
        """Parse the user reply to extract field values for missing fields."""
        if not self.missing_fields:
            return

        next_field = self.missing_fields[0]
        # Simple heuristic: map the raw reply to the next expected field
        value = reply.strip()
        if next_field == "members":
            self.collected_data[next_field] = [m.strip() for m in value.split(",")]
        elif next_field == "action" and value.lower() not in ("accept", "deny", "drop", "allow"):
            # Try to normalize
            if "liberar" in value.lower() or "permitir" in value.lower() or "allow" in value.lower():
                self.collected_data[next_field] = "accept"
            else:
                self.collected_data[next_field] = "deny"
        else:
            self.collected_data[next_field] = value

    def _format_plan_summary(self) -> str:
        if not self.plan:
            return "Erro ao gerar o plano de ação."

        lines = [
            "✅ **Plano de ação gerado.** Confirme antes de executar:\n",
            f"- **Intenção:** {self.plan.intent.value}",
            f"- **Dispositivo:** {self.device.name} ({self.device.vendor.value})",
        ]

        if self.plan.rule_spec:
            r = self.plan.rule_spec
            lines += [
                f"- **Regra:** {r.name}",
                f"- **Origem:** {r.src_address} (zona: {r.src_zone})",
                f"- **Destino:** {r.dst_address} (zona: {r.dst_zone})",
                f"- **Serviço:** {r.service}",
                f"- **Ação:** {r.action}",
                f"- **Comentário:** {r.comment or '(nenhum)'}",
            ]

        if self.plan.nat_spec:
            n = self.plan.nat_spec
            lines += [
                f"- **NAT:** {n.name}",
                f"- **Entrada:** {n.inbound_interface} → Saída: {n.outbound_interface}",
                f"- **Origem:** {n.source} → {n.translated_source}",
                f"- **Destino:** {n.destination} → {n.translated_destination}",
                f"- **Serviço:** {n.service} → {n.translated_service}",
            ]

        if self.plan.route_spec:
            rt = self.plan.route_spec
            lines += [
                f"- **Rota:** {rt.name or '(sem nome)'}",
                f"- **Interface:** {rt.interface}",
                f"- **Destino:** {rt.destination}",
                f"- **Gateway:** {rt.gateway}",
                f"- **Métrica:** {rt.metric}",
            ]

        if self.plan.group_spec:
            g = self.plan.group_spec
            lines += [
                f"- **Grupo:** {g.name}",
                f"- **Membros:** {', '.join(g.members)}",
            ]

        if self.plan.content_filter_spec:
            cf = self.plan.content_filter_spec
            lines += [
                f"- **Perfil CFS:** {cf.profile_name}",
                f"- **Política CFS:** {cf.policy_name or '(automático)'}",
                f"- **Categorias bloqueadas:** {', '.join(cf.blocked_categories) or '(nenhuma)'}",
                f"- **Sites permitidos:** {', '.join(cf.allowed_sites) or '(nenhum)'}",
                f"- **Sites bloqueados:** {', '.join(cf.blocked_sites) or '(nenhum)'}",
                f"- **Origem:** {cf.source_address}",
                f"- **Zonas:** {', '.join(cf.zones)} → WAN",
            ]
            flags_on = [
                label for flag, label in [
                    (cf.https_filtering, "HTTPS Filtering"),
                    (cf.smart_filter, "Smart Filtering"),
                    (cf.safe_search, "Safe Search"),
                    (cf.threat_api, "Threat API"),
                    (cf.google_safe_search, "Google Force Safe Search"),
                    (cf.youtube_restrict_mode, "YouTube Restrict Mode"),
                    (cf.bing_safe_search, "Bing Force Safe Search"),
                    (cf.reputation_enabled, f"Reputation ({cf.reputation_action})"),
                ] if flag
            ]
            if flags_on:
                lines.append(f"- **Recursos ativos:** {', '.join(flags_on)}")
            lines.append("- **Modo de execução:** SSH CLI")

        if self.plan.security_service_spec:
            svc = self.plan.security_service_spec
            lines += [
                f"- **Serviço:** {svc.service}",
                f"- **Ação:** {'Ativar' if svc.enabled else 'Desativar'}",
            ]

        if self.plan.security_exclusion_spec:
            exc = self.plan.security_exclusion_spec
            lines += [
                f"- **IPs para exclusão:** {', '.join(exc.ip_addresses)}",
                f"- **Serviços:** {', '.join(exc.services) if exc.services else 'todos'}",
                f"- **Zona:** {exc.zone}",
            ]

        if self.plan.app_rules_spec:
            ar = self.plan.app_rules_spec
            lines += [
                f"- **Política App Rules:** {ar.policy_name}",
                f"- **Ação:** {ar.action_object}",
            ]

        if self.plan.ssh_commands:
            lines.append("- **Comandos SSH:**")
            for cmd in self.plan.ssh_commands:
                lines.append(f"  `{cmd}`")

        lines.append("\nDigite **confirmar** para executar ou **cancelar** para abortar.")
        return "\n".join(lines)
