"""Fase 22 — Onboarding orchestration service."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import (
    LifecycleAction, LifecycleTask, ActionStatus, SystemType, TaskStatus,
    IdentityProvider, ProviderType,
)
from app.models.onboarding import ExternalConnector, OnboardingProfile
from app.utils.crypto import decrypt_credentials


async def run_onboarding(db: AsyncSession, action: LifecycleAction, profile: OnboardingProfile) -> None:
    """Execute all onboarding tasks defined in the profile."""
    action.status = ActionStatus.running
    await db.flush()

    for task in action.tasks:
        await _execute_onboarding_task(db, task, action, profile)
        await db.flush()

    all_ok = all(
        t.status in (TaskStatus.success, TaskStatus.skipped)
        for t in action.tasks
    )
    action.status = ActionStatus.completed if all_ok else ActionStatus.failed
    action.completed_at = datetime.now(timezone.utc)
    await db.commit()


async def build_onboarding_tasks(
    db: AsyncSession, action: LifecycleAction, profile: OnboardingProfile
) -> list[LifecycleTask]:
    """Build task list from profile definition."""
    tasks: list[LifecycleTask] = []

    # Tasks from profile systems
    for ps in profile.systems:
        stype = ps.system_type
        try:
            system_type_enum = SystemType(stype)
        except ValueError:
            continue

        tasks.append(LifecycleTask(
            id=uuid4(),
            action_id=action.id,
            system_type=system_type_enum,
            system_id=ps.system_id,
            system_name=ps.system_name,
            status=TaskStatus.pending,
        ))

    # AD group tasks — one task per provider with local_ad type
    if profile.ad_groups:
        from sqlalchemy import select
        providers = (await db.execute(
            select(IdentityProvider).where(
                IdentityProvider.tenant_id == action.tenant_id,
                IdentityProvider.is_active.is_(True),
                IdentityProvider.provider_type == ProviderType.local_ad,
            )
        )).scalars().all()

        for provider in providers:
            tasks.append(LifecycleTask(
                id=uuid4(),
                action_id=action.id,
                system_type=SystemType.local_ad,
                system_id=str(provider.id),
                system_name=f"{provider.name} (grupos AD)",
                status=TaskStatus.pending,
            ))

    return tasks


async def _execute_onboarding_task(
    db: AsyncSession, task: LifecycleTask, action: LifecycleAction, profile: OnboardingProfile
) -> None:
    task.status = TaskStatus.running
    task.executed_at = datetime.now(timezone.utc)

    try:
        if task.system_type == SystemType.local_ad:
            ok, msg = await _onboard_local_ad(db, task.system_id, action, profile)
        elif task.system_type == SystemType.azure_ad:
            ok, msg = await _onboard_azure_ad(db, task.system_id, action, profile)
        elif task.system_type == SystemType.google_workspace:
            ok, msg = await _onboard_google_workspace(db, task.system_id, action, profile)
        elif task.system_type == SystemType.guacamole:
            ok, msg = await _onboard_guacamole(db, task.system_id, action, profile)
        elif task.system_type == SystemType.tactical_rmm:
            ok, msg = await _onboard_tactical_rmm(db, task.system_id, action, profile)
        elif task.system_type == SystemType.unifi:
            ok, msg = await _onboard_unifi(db, task.system_id, action, profile)
        else:
            ok, msg = False, f"Tipo de sistema '{task.system_type}' não suportado para onboarding"
    except Exception as e:
        ok, msg = False, str(e)

    if ok:
        task.status = TaskStatus.success
        task.result = msg
    else:
        task.status = TaskStatus.failed
        task.error = msg


async def _onboard_local_ad(
    db: AsyncSession, provider_id: str, action: LifecycleAction, profile: OnboardingProfile
) -> tuple[bool, str]:
    provider = await db.get(IdentityProvider, UUID(provider_id))
    if not provider:
        return False, "Provider não encontrado"
    config = decrypt_credentials(provider.encrypted_config)

    from app.services.local_ad_service import find_user, add_user_to_groups

    username = action.target_username
    user = await find_user(config, username)
    if not user:
        return False, f"Usuário '{username}' não encontrado no AD Local"

    groups_added = []
    groups_failed = []
    for group in profile.ad_groups:
        try:
            await add_user_to_groups(config, user["dn"], [group])
            groups_added.append(group)
        except Exception as e:
            groups_failed.append(f"{group}: {e}")

    if groups_failed:
        return False, f"Grupos adicionados: {groups_added}. Falhas: {groups_failed}"
    return True, f"Usuário adicionado aos grupos: {', '.join(groups_added)}"


async def _onboard_azure_ad(
    db: AsyncSession, provider_id: str, action: LifecycleAction, profile: OnboardingProfile
) -> tuple[bool, str]:
    provider = await db.get(IdentityProvider, UUID(provider_id))
    if not provider:
        return False, "Provider não encontrado"
    config = decrypt_credentials(provider.encrypted_config)

    # Find the profile system config for azure_ad
    ps_config = _get_profile_system_config(profile, SystemType.azure_ad, provider_id)
    groups = ps_config.get("groups", [])
    if not groups:
        return True, "Nenhum grupo Azure AD configurado no perfil (ignorado)"

    from app.services.azure_ad_service import find_user, add_user_to_groups as azure_add_groups
    user = await find_user(config, action.target_username)
    if not user:
        return False, f"Usuário '{action.target_username}' não encontrado no Azure AD"

    await azure_add_groups(config, user["id"], groups)
    return True, f"Usuário adicionado a {len(groups)} grupo(s) no Azure AD"


async def _onboard_google_workspace(
    db: AsyncSession, provider_id: str, action: LifecycleAction, profile: OnboardingProfile
) -> tuple[bool, str]:
    provider = await db.get(IdentityProvider, UUID(provider_id))
    if not provider:
        return False, "Provider não encontrado"
    config = decrypt_credentials(provider.encrypted_config)

    ps_config = _get_profile_system_config(profile, SystemType.google_workspace, provider_id)
    groups = ps_config.get("groups", [])
    if not groups:
        return True, "Nenhum grupo Google Workspace configurado no perfil (ignorado)"

    from app.services.google_workspace_service import find_user, add_user_to_groups as gws_add_groups
    user = await find_user(config, action.target_username)
    if not user:
        return False, f"Usuário '{action.target_username}' não encontrado no Google Workspace"

    email = user.get("primaryEmail", action.target_username)
    await gws_add_groups(config, email, groups)
    return True, f"Usuário adicionado a {len(groups)} grupo(s) no Google Workspace"


async def _onboard_guacamole(
    db: AsyncSession, connector_id: str | None, action: LifecycleAction, profile: OnboardingProfile
) -> tuple[bool, str]:
    if not connector_id:
        return False, "Conector Guacamole não configurado"
    connector = await db.get(ExternalConnector, UUID(connector_id))
    if not connector:
        return False, "Conector não encontrado"
    config = decrypt_credentials(connector.encrypted_config)

    ps_config = _get_profile_system_config(profile, SystemType.guacamole, connector_id)
    temp_password = ps_config.get("temp_password", "Mudar@123")

    from app.services.guacamole_service import get_user, create_user
    existing = await get_user(config, action.target_username)
    if existing:
        return True, f"Usuário já existe no Guacamole (ignorado)"

    await create_user(
        config,
        username=action.target_username,
        password=temp_password,
        display_name=action.display_name,
    )
    return True, f"Usuário criado no Guacamole (senha temporária configurada)"


async def _onboard_tactical_rmm(
    db: AsyncSession, connector_id: str | None, action: LifecycleAction, profile: OnboardingProfile
) -> tuple[bool, str]:
    if not connector_id:
        return False, "Conector Tactical RMM não configurado"
    connector = await db.get(ExternalConnector, UUID(connector_id))
    if not connector:
        return False, "Conector não encontrado"
    config = decrypt_credentials(connector.encrypted_config)

    ps_config = _get_profile_system_config(profile, SystemType.tactical_rmm, connector_id)
    role = ps_config.get("role", "user")
    temp_password = ps_config.get("temp_password", "Mudar@123")

    from app.services.tactical_rmm_service import get_user, create_user
    existing = await get_user(config, action.target_username)
    if existing:
        return True, "Usuário já existe no Tactical RMM (ignorado)"

    email = action.email or f"{action.target_username}@empresa.local"
    await create_user(config, action.target_username, email, temp_password, role)
    return True, f"Usuário criado no Tactical RMM com role '{role}'"


async def _onboard_unifi(
    db: AsyncSession, connector_id: str | None, action: LifecycleAction, profile: OnboardingProfile
) -> tuple[bool, str]:
    if not connector_id:
        return False, "Conector Unifi não configurado"
    connector = await db.get(ExternalConnector, UUID(connector_id))
    if not connector:
        return False, "Conector não encontrado"
    config = decrypt_credentials(connector.encrypted_config)

    ps_config = _get_profile_system_config(profile, SystemType.unifi, connector_id)
    role = ps_config.get("role", "readonly")
    email = action.email or f"{action.target_username}@empresa.local"

    from app.services.unifi_service import get_admin, invite_admin
    existing = await get_admin(config, action.target_username)
    if existing:
        return True, "Admin já existe no Unifi (ignorado)"

    await invite_admin(config, action.target_username, email, role)
    return True, f"Convite enviado para admin Unifi com role '{role}'"


def _get_profile_system_config(profile: OnboardingProfile, system_type: SystemType, system_id: str | None) -> dict:
    for ps in profile.systems:
        if ps.system_type == system_type.value and ps.system_id == system_id:
            return ps.config or {}
    return {}
