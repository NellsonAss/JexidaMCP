"""Tests for unifi_apply_changes tool and diff helpers."""

import pytest
from unittest.mock import AsyncMock, patch

from mcp_tools.unifi.changes import (
    unifi_apply_changes,
    UniFiApplyChangesInput,
    WifiEdit,
    FirewallEdit,
    UpnpEdit,
)
from mcp_tools.unifi.diff import (
    ChangeAction,
    ConfigChange,
    DiffResult,
    FieldChange,
    plan_wifi_changes,
    plan_firewall_changes,
    plan_vlan_changes,
    plan_upnp_changes,
    combine_diffs,
)


class TestPlanWifiChanges:
    """Tests for WiFi change planning."""
    
    def test_no_changes_needed(self):
        """Test when no changes are needed."""
        current = [
            {"_id": "wlan1", "name": "HomeNet", "enabled": True, "security": "wpapsk"}
        ]
        desired = []
        
        result = plan_wifi_changes(current, desired)
        
        assert result.has_changes is False
        assert len(result.changes) == 0
    
    def test_update_existing_wlan(self):
        """Test updating an existing WLAN."""
        current = [
            {
                "_id": "wlan1",
                "name": "HomeNet",
                "enabled": True,
                "security": "wpapsk",
                "wpa_mode": "wpa2",
            }
        ]
        desired = [
            {"ssid": "HomeNet", "wpa_mode": "wpa3", "wpa3_support": True}
        ]
        
        result = plan_wifi_changes(current, desired)
        
        assert result.has_changes is True
        assert len(result.changes) == 1
        assert result.changes[0].action == ChangeAction.UPDATE
        assert result.changes[0].item_name == "HomeNet"
        
        # Check field changes
        field_names = [c.field for c in result.changes[0].changes]
        assert "wpa_mode" in field_names
        assert "wpa3_support" in field_names
    
    def test_create_new_wlan(self):
        """Test creating a new WLAN."""
        current = []
        desired = [{"ssid": "NewNetwork", "security": "wpapsk"}]
        
        result = plan_wifi_changes(current, desired)
        
        assert result.has_changes is True
        assert len(result.changes) == 1
        assert result.changes[0].action == ChangeAction.CREATE


class TestPlanFirewallChanges:
    """Tests for firewall change planning."""
    
    def test_create_firewall_rule(self):
        """Test creating a new firewall rule."""
        current = {"wan_in": [], "lan_in": []}
        desired = [
            {
                "action": "create",
                "ruleset": "wan_in",
                "rule_name": "Block SSH",
                "rule_action": "drop",
                "protocol": "tcp",
                "dst_port": "22",
            }
        ]
        
        result = plan_firewall_changes(current, desired)
        
        assert result.has_changes is True
        assert len(result.changes) == 1
        assert result.changes[0].action == ChangeAction.CREATE
    
    def test_update_firewall_rule(self):
        """Test updating an existing firewall rule."""
        current = {
            "wan_in": [
                {
                    "_id": "fw1",
                    "name": "Allow HTTPS",
                    "action": "accept",
                    "protocol": "tcp",
                    "dst_port": "443",
                }
            ],
            "lan_in": [],
        }
        desired = [
            {
                "action": "update",
                "rule_id": "fw1",
                "enabled": False,
            }
        ]
        
        result = plan_firewall_changes(current, desired)
        
        assert result.has_changes is True
        assert result.changes[0].action == ChangeAction.UPDATE
    
    def test_delete_firewall_rule(self):
        """Test deleting a firewall rule."""
        current = {"wan_in": [{"_id": "fw1", "name": "Old Rule"}]}
        desired = [{"action": "delete", "rule_id": "fw1"}]
        
        result = plan_firewall_changes(current, desired)
        
        assert result.has_changes is True
        assert result.changes[0].action == ChangeAction.DELETE


class TestPlanUpnpChanges:
    """Tests for UPnP change planning."""
    
    def test_disable_upnp(self):
        """Test disabling UPnP."""
        current = {"upnp_enabled": True, "upnp_nat_pmp_enabled": True}
        desired = {"upnp_enabled": False, "upnp_nat_pmp_enabled": False}
        
        result = plan_upnp_changes(current, desired)
        
        assert result.has_changes is True
        assert len(result.changes) == 1
        
        field_names = [c.field for c in result.changes[0].changes]
        assert "upnp_enabled" in field_names
        assert "upnp_nat_pmp_enabled" in field_names
    
    def test_no_upnp_changes(self):
        """Test when UPnP already matches desired state."""
        current = {"upnp_enabled": False}
        desired = {"upnp_enabled": False}
        
        result = plan_upnp_changes(current, desired)
        
        assert result.has_changes is False


class TestCombineDiffs:
    """Tests for combining multiple diffs."""
    
    def test_combine_empty_diffs(self):
        """Test combining empty diffs."""
        diff1 = DiffResult()
        diff2 = DiffResult()
        
        combined = combine_diffs(diff1, diff2)
        
        assert combined.has_changes is False
        assert len(combined.changes) == 0
    
    def test_combine_multiple_diffs(self):
        """Test combining multiple diffs with changes."""
        diff1 = DiffResult(
            changes=[
                ConfigChange(
                    action=ChangeAction.UPDATE,
                    item_type="wifi",
                    item_id="w1",
                    item_name="Net1",
                )
            ],
            has_changes=True,
            summary="1 WiFi change",
        )
        diff2 = DiffResult(
            changes=[
                ConfigChange(
                    action=ChangeAction.UPDATE,
                    item_type="upnp",
                    item_id="u1",
                    item_name="UPnP",
                )
            ],
            has_changes=True,
            summary="1 UPnP change",
        )
        
        combined = combine_diffs(diff1, diff2)
        
        assert combined.has_changes is True
        assert len(combined.changes) == 2
        assert "WiFi" in combined.summary
        assert "UPnP" in combined.summary


class TestUniFiApplyChanges:
    """Tests for unifi_apply_changes tool."""
    
    @pytest.mark.asyncio
    async def test_dry_run_returns_diff(self):
        """Test dry run mode returns diff without applying."""
        with patch("mcp_tools.unifi.changes.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_wlans = AsyncMock(return_value=[
                {"_id": "w1", "name": "TestNet", "enabled": True, "wpa_mode": "wpa2"}
            ])
            mock_client.get_firewall_rules = AsyncMock(return_value={})
            mock_client.get_networks = AsyncMock(return_value=[])
            mock_client.get_upnp_settings = AsyncMock(return_value={
                "upnp_enabled": True
            })
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client
            
            params = UniFiApplyChangesInput(
                dry_run=True,
                wifi_edits=[WifiEdit(ssid="TestNet", wpa_mode="wpa3")],
            )
            
            result = await unifi_apply_changes(params)
            
            assert result.success is True
            assert result.dry_run is True
            assert result.diff["has_changes"] is True
            # Should not have applied anything
            assert len(result.results) == 0
    
    @pytest.mark.asyncio
    async def test_apply_changes_success(self):
        """Test applying changes successfully."""
        with patch("mcp_tools.unifi.changes.UniFiClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get_wlans = AsyncMock(return_value=[
                {"_id": "w1", "name": "TestNet", "enabled": True}
            ])
            mock_client.get_firewall_rules = AsyncMock(return_value={})
            mock_client.get_networks = AsyncMock(return_value=[])
            mock_client.get_upnp_settings = AsyncMock(return_value={
                "upnp_enabled": True
            })
            mock_client.update_upnp_settings = AsyncMock(return_value={})
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client
            
            params = UniFiApplyChangesInput(
                dry_run=False,
                upnp_edits=UpnpEdit(upnp_enabled=False),
            )
            
            result = await unifi_apply_changes(params)
            
            assert result.success is True
            assert result.dry_run is False
            assert result.changes_applied >= 0


class TestFieldChange:
    """Tests for FieldChange dataclass."""
    
    def test_to_dict(self):
        """Test FieldChange to_dict conversion."""
        change = FieldChange(
            field="enabled",
            old_value=True,
            new_value=False,
        )
        
        result = change.to_dict()
        
        assert result["field"] == "enabled"
        assert result["old_value"] is True
        assert result["new_value"] is False


class TestConfigChange:
    """Tests for ConfigChange dataclass."""
    
    def test_to_dict(self):
        """Test ConfigChange to_dict conversion."""
        change = ConfigChange(
            action=ChangeAction.UPDATE,
            item_type="wifi",
            item_id="w1",
            item_name="MyNet",
            changes=[
                FieldChange(field="enabled", old_value=True, new_value=False)
            ],
        )
        
        result = change.to_dict()
        
        assert result["action"] == "update"
        assert result["item_type"] == "wifi"
        assert result["item_name"] == "MyNet"
        assert len(result["changes"]) == 1

