"""Fase 26 — Celery task for applying a GoldenBundle to a Device."""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="workers.apply_golden_bundle")
def apply_golden_bundle(self, bundle_apply_id: str) -> None:
    """Celery task: apply a GoldenBundle to a Device."""
    asyncio.get_event_loop().run_until_complete(_apply(bundle_apply_id))


async def _apply(bundle_apply_id: str) -> None:  # noqa: C901
    from datetime import datetime, timezone

    from app.database import AsyncSessionLocal
    from app.models.golden_bundle import ApplyStrategy, BundleApply
    from app.models.device import Device
    from app.services.bundle_renderer import merge_variables, render_rest_payload
    from app.services.fortinet_rest_apply import FortinetRestApply
    from app.utils.crypto import decrypt_credentials

    async with AsyncSessionLocal() as db:
        apply_rec = await db.get(BundleApply, UUID(bundle_apply_id))
        if not apply_rec:
            logger.warning("BundleApply %s not found", bundle_apply_id)
            return

        bundle = apply_rec.bundle  # eagerly loaded via selectin
        device = await db.get(Device, apply_rec.device_id)
        if not device:
            logger.error("Device %s not found for BundleApply %s", apply_rec.device_id, bundle_apply_id)
            apply_rec.status = "failed"
            apply_rec.section_results = {"error": "device not found"}
            apply_rec.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return

        creds = decrypt_credentials(device.encrypted_credentials)
        base_url = f"{'https' if device.use_ssl else 'http'}://{device.host}:{device.port}"

        variables = merge_variables(
            bundle.variables or {},
            {},  # device-level variables would be fetched from template_variables
            apply_rec.variables_used or {},
        )

        section_results: dict = {}
        overall_ok = True

        for section in bundle.sections:
            section_id = str(section.id)
            try:
                if section.apply_strategy == ApplyStrategy.rest_api and section.rest_payload_template:
                    payload = render_rest_payload(section.rest_payload_template, variables)

                    if device.vendor.value == "fortinet":
                        applier = FortinetRestApply(
                            host=base_url,
                            token=creds.get("token", ""),
                            vdom=creds.get("vdom") or "root",
                            verify_ssl=device.verify_ssl,
                        )

                        if section.section_type == "objects":
                            result = await applier.apply_address_objects(payload.get("objects", [payload]))
                        elif section.section_type == "access_rules":
                            result = await applier.apply_policies(payload.get("policies", [payload]))
                        elif section.section_type == "content_filter":
                            result = await applier.apply_webfilter_profile(payload)
                        elif section.section_type == "geo_ip":
                            result = await applier.apply_geo_ip(payload.get("countries", []))
                        elif section.section_type == "vpn":
                            result = await applier.apply_ipsec_vpn(
                                payload.get("phase1", {}),
                                payload.get("phase2", {}),
                            )
                        else:
                            result = {"status": "skipped", "reason": "unhandled section_type", "ok": False}
                    else:
                        result = {
                            "status": "skipped",
                            "reason": f"REST apply not implemented for {device.vendor}",
                            "ok": False,
                        }

                    section_results[section_id] = {
                        "status": "ok" if result.get("ok") else "failed",
                        "result": result,
                    }
                    if not result.get("ok"):
                        overall_ok = False

                elif section.apply_strategy == ApplyStrategy.cli_ssh:
                    section_results[section_id] = {
                        "status": "skipped",
                        "reason": "cli_ssh sections run separately",
                    }
                else:
                    section_results[section_id] = {
                        "status": "skipped",
                        "reason": "manual_only",
                    }

            except Exception as exc:
                logger.exception("Error applying section %s", section_id)
                section_results[section_id] = {"status": "failed", "error": str(exc)}
                overall_ok = False

        apply_rec.status = "applied" if overall_ok else "failed"
        apply_rec.section_results = section_results
        apply_rec.completed_at = datetime.now(timezone.utc)
        await db.commit()
