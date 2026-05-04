"""Tests for Operation risk classification — classify_risk() and OperationRisk enum."""
import pytest

from app.models.operation import OperationRisk, classify_risk


class TestClassifyRiskCritical:
    def test_direct_ssh_is_critical_with_two_approvals(self):
        risk, approvals = classify_risk("direct_ssh")
        assert risk == OperationRisk.critical
        assert approvals == 2

    def test_critical_is_the_only_tier_requiring_multi_sig(self):
        # Verify no other standard intent accidentally gets 2 approvals
        for intent in ("delete_rule", "create_rule", "list_rules", "edit_rule"):
            _, approvals = classify_risk(intent)
            assert approvals == 1, f"Unexpected multi-sig for intent '{intent}'"


class TestClassifyRiskHigh:
    @pytest.mark.parametrize("intent", [
        "delete_rule",
        "delete_nat_policy",
        "delete_route_policy",
        "delete_vlan",
    ])
    def test_high_risk_intents(self, intent: str):
        risk, approvals = classify_risk(intent)
        assert risk == OperationRisk.high
        assert approvals == 1

    def test_high_risk_single_approval_only(self):
        risk, approvals = classify_risk("delete_rule")
        assert approvals == 1


class TestClassifyRiskLow:
    @pytest.mark.parametrize("intent", [
        "list_rules",
        "list_nat_policies",
        "list_route_policies",
        "get_security_status",
        "health_check",
        "get_snapshot",
        "list_vlans",
        "list_ports",
        "get_info",
    ])
    def test_low_risk_read_only_intents(self, intent: str):
        risk, approvals = classify_risk(intent)
        assert risk == OperationRisk.low
        assert approvals == 1


class TestClassifyRiskMedium:
    @pytest.mark.parametrize("intent", [
        "create_rule",
        "edit_rule",
        "create_nat_policy",
        "edit_nat_policy",
        "create_route_policy",
        "create_vlan",
        "configure_vpn",
        "some_unknown_future_intent",
    ])
    def test_medium_risk_create_and_edit_intents(self, intent: str):
        risk, approvals = classify_risk(intent)
        assert risk == OperationRisk.medium
        assert approvals == 1

    def test_none_intent_defaults_to_medium(self):
        risk, approvals = classify_risk(None)
        assert risk == OperationRisk.medium
        assert approvals == 1

    def test_empty_string_defaults_to_medium(self):
        # Empty string is falsy — treated same as None
        risk, approvals = classify_risk("")
        assert risk == OperationRisk.medium
        assert approvals == 1


class TestOperationRiskEnum:
    def test_all_enum_values_are_strings(self):
        assert OperationRisk.low.value == "low"
        assert OperationRisk.medium.value == "medium"
        assert OperationRisk.high.value == "high"
        assert OperationRisk.critical.value == "critical"

    def test_enum_is_str_subclass(self):
        assert isinstance(OperationRisk.critical, str)

    def test_four_tiers_defined(self):
        values = {r.value for r in OperationRisk}
        assert values == {"low", "medium", "high", "critical"}

    def test_classify_risk_return_type(self):
        result = classify_risk("list_rules")
        assert isinstance(result, tuple)
        assert len(result) == 2
        risk, approvals = result
        assert isinstance(risk, OperationRisk)
        assert isinstance(approvals, int)
