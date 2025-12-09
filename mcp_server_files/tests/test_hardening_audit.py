"""Tests for network_hardening_audit and network_apply_hardening_plan tools."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from mcp_tools.unifi.audit import (
    network_hardening_audit,
    NetworkHardeningAuditInput,
    PolicyEvaluator,
    Severity,
    Finding,
    load_policy,
)
from mcp_tools.unifi.hardening import (
    network_apply_hardening_plan,
    NetworkApplyHardeningPlanInput,
    HardeningPlan,
    RecommendedChange,
    group_changes_by_phase,
    convert_to_edits,
)


class TestPolicyEvaluator:
    """Tests for PolicyEvaluator."""
    
    def test_evaluate_open_wifi(self):
        """Test detection of open WiFi networks."""
        policy = {
            "wifi": {
                "require_encryption": {"enabled": True, "severity": "high"},
                "disallow_open_except": {"allowed_ssids": []},
            }
        }
        
        evaluator = PolicyEvaluator(policy)
        evaluator.evaluate_wifi([
            {
                "name": "OpenNetwork",
                "enabled": True,
                "security": "open",
                "is_guest": False,
            }
        ])
        
        findings, recommendations = evaluator.get_results()
        
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH
        assert "open" in findings[0].title.lower()
        assert len(recommendations) == 1
    
    def test_evaluate_guest_without_isolation(self):
        """Test detection of guest network without client isolation."""
        policy = {
            "wifi": {
                "require_client_isolation_for_guest": {"enabled": True, "severity": "medium"},
            }
        }
        
        evaluator = PolicyEvaluator(policy)
        evaluator.evaluate_wifi([
            {
                "name": "GuestNet",
                "enabled": True,
                "security": "wpapsk",
                "is_guest": True,
                "l2_isolation": False,
            }
        ])
        
        findings, recommendations = evaluator.get_results()
        
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM
        assert "isolation" in findings[0].title.lower()
    
    def test_evaluate_upnp_enabled(self):
        """Test detection of UPnP enabled."""
        policy = {
            "remote_access": {
                "upnp_allowed": {"enabled": False, "severity": "high"},
            }
        }
        
        evaluator = PolicyEvaluator(policy)
        evaluator.evaluate_remote_access({
            "upnp_enabled": True,
            "upnp_nat_pmp_enabled": False,
        })
        
        findings, recommendations = evaluator.get_results()
        
        assert len(findings) == 1
        assert findings[0].severity == Severity.HIGH
        assert "upnp" in findings[0].title.lower()
        
        # Should have recommendation to disable
        assert len(recommendations) == 1
        assert recommendations[0].changes.get("upnp_enabled") is False
    
    def test_evaluate_ids_disabled(self):
        """Test detection of IDS/IPS disabled."""
        policy = {
            "threat_management": {
                "require_ids_ips": {"enabled": True, "severity": "medium", "recommended_mode": "ips"},
            }
        }
        
        evaluator = PolicyEvaluator(policy)
        evaluator.evaluate_threat_management({
            "ids_ips_enabled": False,
            "mode": "disabled",
        })
        
        findings, _ = evaluator.get_results()
        
        assert len(findings) == 1
        assert findings[0].severity == Severity.MEDIUM
        assert "ids" in findings[0].title.lower() or "ips" in findings[0].title.lower()
    
    def test_no_findings_for_compliant_config(self):
        """Test no findings when config is compliant."""
        policy = {
            "wifi": {
                "require_encryption": {"enabled": True, "severity": "high"},
            },
            "remote_access": {
                "upnp_allowed": {"enabled": False, "severity": "high"},
            },
        }
        
        evaluator = PolicyEvaluator(policy)
        evaluator.evaluate_wifi([
            {
                "name": "SecureNet",
                "enabled": True,
                "security": "wpapsk",
                "wpa_mode": "wpa3",
                "is_guest": False,
            }
        ])
        evaluator.evaluate_remote_access({
            "upnp_enabled": False,
        })
        
        findings, _ = evaluator.get_results()
        
        assert len(findings) == 0


class TestNetworkHardeningAudit:
    """Tests for network_hardening_audit tool."""
    
    @pytest.mark.asyncio
    async def test_audit_success(self):
        """Test successful audit execution."""
        with patch("mcp_tools.unifi.audit.UniFiClient") as MockClient, \
             patch("mcp_tools.unifi.audit.load_policy") as mock_policy:
            
            mock_policy.return_value = {
                "wifi": {"require_encryption": {"enabled": True, "severity": "high"}},
                "remote_access": {"upnp_allowed": {"enabled": False, "severity": "high"}},
            }
            
            mock_client = AsyncMock()
            mock_client.get_wlans = AsyncMock(return_value=[
                {"name": "OpenNet", "enabled": True, "security": "open", "is_guest": False}
            ])
            mock_client.get_networks = AsyncMock(return_value=[])
            mock_client.get_firewall_rules = AsyncMock(return_value={})
            mock_client.get_upnp_settings = AsyncMock(return_value={"upnp_enabled": True})
            mock_client.get_mgmt_settings = AsyncMock(return_value={})
            mock_client.get_threat_management_settings = AsyncMock(return_value={})
            mock_client.get_dpi_settings = AsyncMock(return_value={})
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client
            
            params = NetworkHardeningAuditInput()
            result = await network_hardening_audit(params)
            
            assert result.success is True
            assert len(result.findings) > 0
            assert result.findings_by_severity["high"] > 0
    
    @pytest.mark.asyncio
    async def test_audit_with_scan(self):
        """Test audit with network scan."""
        with patch("mcp_tools.unifi.audit.UniFiClient") as MockClient, \
             patch("mcp_tools.unifi.audit.load_policy") as mock_policy, \
             patch("mcp_tools.unifi.audit.network_scan_local") as mock_scan:
            
            mock_policy.return_value = {}
            
            mock_client = AsyncMock()
            mock_client.get_wlans = AsyncMock(return_value=[])
            mock_client.get_networks = AsyncMock(return_value=[])
            mock_client.get_firewall_rules = AsyncMock(return_value={})
            mock_client.get_upnp_settings = AsyncMock(return_value={})
            mock_client.get_mgmt_settings = AsyncMock(return_value={})
            mock_client.get_threat_management_settings = AsyncMock(return_value={})
            mock_client.get_dpi_settings = AsyncMock(return_value={})
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client
            
            mock_scan_result = MagicMock()
            mock_scan_result.success = True
            mock_scan_result.hosts_up = 5
            mock_scan_result.hosts = []
            mock_scan.return_value = mock_scan_result
            
            params = NetworkHardeningAuditInput(
                run_scan=True,
                scan_subnets=["192.168.1.0/24"],
            )
            result = await network_hardening_audit(params)
            
            assert result.success is True
            assert result.scan_results is not None
            assert "hosts_found" in result.scan_results


class TestGroupChangesByPhase:
    """Tests for change phase grouping."""
    
    def test_group_changes(self):
        """Test grouping changes by phase."""
        changes = [
            RecommendedChange(
                category="upnp",
                change_type="update",
                target="upnp",
                changes={"upnp_enabled": False},
                finding_ids=["F001"],
                phase=1,
            ),
            RecommendedChange(
                category="firewall",
                change_type="create",
                target="rule1",
                changes={},
                finding_ids=["F002"],
                phase=2,
            ),
            RecommendedChange(
                category="wifi",
                change_type="update",
                target="ssid1",
                changes={},
                finding_ids=["F003"],
                phase=1,
            ),
        ]
        
        grouped = group_changes_by_phase(changes)
        
        assert 1 in grouped
        assert 2 in grouped
        assert len(grouped[1]) == 2
        assert len(grouped[2]) == 1


class TestConvertToEdits:
    """Tests for converting recommendations to edits."""
    
    def test_convert_wifi_edit(self):
        """Test converting WiFi recommendation to edit."""
        changes = [
            RecommendedChange(
                category="wifi",
                change_type="update",
                target="TestNet",
                changes={"ssid": "TestNet", "l2_isolation": True},
                finding_ids=["F001"],
                phase=1,
            )
        ]
        
        wifi_edits, firewall_edits, vlan_edits, upnp_edit = convert_to_edits(changes)
        
        assert len(wifi_edits) == 1
        assert wifi_edits[0].ssid == "TestNet"
        assert wifi_edits[0].l2_isolation is True
    
    def test_convert_upnp_edit(self):
        """Test converting UPnP recommendation to edit."""
        changes = [
            RecommendedChange(
                category="upnp",
                change_type="update",
                target="upnp",
                changes={"upnp_enabled": False},
                finding_ids=["F001"],
                phase=1,
            )
        ]
        
        wifi_edits, firewall_edits, vlan_edits, upnp_edit = convert_to_edits(changes)
        
        assert upnp_edit is not None
        assert upnp_edit.upnp_enabled is False


class TestNetworkApplyHardeningPlan:
    """Tests for network_apply_hardening_plan tool."""
    
    @pytest.mark.asyncio
    async def test_preview_mode(self):
        """Test preview mode (confirm=False)."""
        params = NetworkApplyHardeningPlanInput(
            plan=HardeningPlan(changes=[
                RecommendedChange(
                    category="upnp",
                    change_type="update",
                    target="upnp",
                    changes={"upnp_enabled": False},
                    finding_ids=["F001"],
                    phase=1,
                )
            ]),
            confirm=False,
        )
        
        result = await network_apply_hardening_plan(params)
        
        assert result.success is True
        assert result.preview_only is True
        assert len(result.phases) == 1
        assert result.phases[0].applied is False
    
    @pytest.mark.asyncio
    async def test_apply_phased(self):
        """Test phased application."""
        with patch("mcp_tools.unifi.hardening.UniFiClient") as MockClient, \
             patch("mcp_tools.unifi.hardening.unifi_apply_changes") as mock_apply:
            
            mock_client = AsyncMock()
            mock_client.get_devices = AsyncMock(return_value=[])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client
            
            mock_apply_result = MagicMock()
            mock_apply_result.success = True
            mock_apply_result.changes_applied = 1
            mock_apply_result.changes_failed = 0
            mock_apply_result.warnings = []
            mock_apply.return_value = mock_apply_result
            
            params = NetworkApplyHardeningPlanInput(
                plan=HardeningPlan(changes=[
                    RecommendedChange(
                        category="upnp",
                        change_type="update",
                        target="upnp",
                        changes={"upnp_enabled": False},
                        finding_ids=["F001"],
                        phase=1,
                    )
                ]),
                confirm=True,
                phased=True,
            )
            
            result = await network_apply_hardening_plan(params)
            
            assert result.success is True
            assert result.preview_only is False
            assert result.total_applied == 1
    
    @pytest.mark.asyncio
    async def test_empty_plan(self):
        """Test handling of empty plan."""
        params = NetworkApplyHardeningPlanInput(
            plan=HardeningPlan(changes=[]),
            confirm=True,
        )
        
        result = await network_apply_hardening_plan(params)
        
        assert result.success is True
        assert result.total_changes == 0
        assert "No changes" in result.warnings[0]

