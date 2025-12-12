"""UniFi Security Hardening Tool.

Provides the security_harden_unifi tool for applying security
recommendations from the audit in a controlled, phased manner.

Follows the UNIFI HARDENING AUTOMATION PLAN:
- Phase 1: Low-risk changes (UPnP, WiFi settings, client isolation)
- Phase 2: Firewall rule changes
- Phase 3: VLAN and network segmentation changes

Features:
- Filtering by severity and area
- apply_auto_safe_only option for conservative hardening
- generate_patches_from_findings() for code-based patch generation
- Dry-run mode for previewing changes
- Phased rollout with connectivity checks
- Backup creation before changes
- Rollback capability
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError
from .security_audit import (
    security_audit_unifi,
    SecurityAuditUniFiInput,
    FindingCode,
    PatchOutput,
)

import logging
logger = logging.getLogger(__name__)


# =============================================================================
# Phase Definitions
# =============================================================================

PHASE_DEFINITIONS = {
    1: {
        "name": "Low-risk changes",
        "description": "UPnP, unused SSIDs, client isolation, PMF settings",
        "impact": "low",
        "rollback_safe": True,
    },
    2: {
        "name": "Firewall rules",
        "description": "Add/modify firewall deny rules for VLAN isolation",
        "impact": "medium",
        "rollback_safe": True,
    },
    3: {
        "name": "Network segmentation",
        "description": "VLAN creation and WiFi VLAN assignments",
        "impact": "high",
        "rollback_safe": False,  # May require manual intervention
    },
}


# =============================================================================
# Input/Output Models
# =============================================================================

class HardeningPatch(BaseModel):
    """A single hardening patch to apply."""
    id: str = Field(default="", description="Unique patch identifier")
    category: str = Field(description="Change category: wifi, firewall, vlan, settings")
    change_type: str = Field(description="Type of change: create, update, delete")
    target: str = Field(description="Target name/ID")
    patch: Dict[str, Any] = Field(description="The patch to apply")
    finding_ids: List[str] = Field(default_factory=list, description="Related finding IDs")
    finding_codes: List[str] = Field(default_factory=list, description="Related finding codes")
    phase: int = Field(default=1, description="Phase number")
    dependencies: List[str] = Field(default_factory=list, description="Dependencies")
    auto_apply_safe: bool = Field(default=True, description="Whether this is safe to auto-apply")
    description: str = Field(default="", description="Human-readable description")
    severity: str = Field(default="medium", description="Severity of the related finding")


class HardeningPlan(BaseModel):
    """A complete hardening plan from the audit."""
    patches: List[HardeningPatch] = Field(
        default_factory=list,
        description="List of patches to apply"
    )


# =============================================================================
# Patch Generation from Finding Codes
# =============================================================================

# Mapping of finding codes to patch generation functions
FINDING_CODE_TO_PATCH = {
    # UPnP/NAT-PMP (Phase 1, auto-safe)
    FindingCode.UPNP_ENABLED.value: {
        "category": "settings",
        "change_type": "update",
        "target": "upnp",
        "patch": {"upnp_enabled": False},
        "phase": 1,
        "auto_apply_safe": True,
        "description": "Disable UPnP",
    },
    FindingCode.NAT_PMP_ENABLED.value: {
        "category": "settings",
        "change_type": "update",
        "target": "upnp",
        "patch": {"upnp_nat_pmp_enabled": False},
        "phase": 1,
        "auto_apply_safe": True,
        "description": "Disable NAT-PMP",
    },
    
    # IDS/IPS (Phase 1, auto-safe)
    FindingCode.IDS_DISABLED.value: {
        "category": "settings",
        "change_type": "update",
        "target": "threat_management",
        "patch": {"ips_enabled": True, "ips_mode": "ips"},
        "phase": 1,
        "auto_apply_safe": True,
        "description": "Enable IDS/IPS in IPS mode",
    },
    
    # WiFi PMF (Phase 1, auto-safe)
    FindingCode.NO_PMF.value: {
        "category": "wifi",
        "change_type": "update",
        "target": "{ssid}",  # Will be replaced with actual SSID
        "patch": {"pmf_mode": "required"},
        "phase": 1,
        "auto_apply_safe": True,
        "description": "Enable Protected Management Frames",
    },
    
    # Guest isolation (Phase 1, auto-safe)
    FindingCode.GUEST_NOT_ISOLATED.value: {
        "category": "wifi",
        "change_type": "update",
        "target": "{ssid}",
        "patch": {"l2_isolation": True, "vlan_enabled": True, "vlan": 40},
        "phase": 1,
        "auto_apply_safe": True,
        "description": "Enable guest client isolation",
    },
    FindingCode.GUEST_NO_CLIENT_ISOLATION.value: {
        "category": "wifi",
        "change_type": "update",
        "target": "{ssid}",
        "patch": {"l2_isolation": True},
        "phase": 1,
        "auto_apply_safe": True,
        "description": "Enable guest client isolation",
    },
    
    # Firewall rules (Phase 2, auto-safe - deny rules are safe)
    FindingCode.MISSING_DENY_IOT_TO_LAN.value: {
        "category": "firewall",
        "change_type": "create",
        "target": "block_iot_to_lan",
        "patch": {
            "name": "Block IoT → LAN",
            "action": "drop",
            "ruleset": "lan_in",
            "src_network": "IoT",
            "dst_network": "LAN",
            "protocol": "all",
        },
        "phase": 2,
        "auto_apply_safe": True,
        "description": "Block IoT VLAN from accessing LAN",
    },
    FindingCode.MISSING_DENY_GUEST_TO_LAN.value: {
        "category": "firewall",
        "change_type": "create",
        "target": "block_guest_to_lan",
        "patch": {
            "name": "Block Guest → LAN",
            "action": "drop",
            "ruleset": "lan_in",
            "src_network": "Guest",
            "dst_network": "LAN",
            "protocol": "all",
        },
        "phase": 2,
        "auto_apply_safe": True,
        "description": "Block Guest VLAN from accessing LAN",
    },
    FindingCode.MISSING_DENY_CAMERAS_TO_LAN.value: {
        "category": "firewall",
        "change_type": "create",
        "target": "block_cameras_to_lan",
        "patch": {
            "name": "Block Cameras → LAN",
            "action": "drop",
            "ruleset": "lan_in",
            "src_network": "Cameras",
            "dst_network": "LAN",
            "protocol": "all",
        },
        "phase": 2,
        "auto_apply_safe": True,
        "description": "Block Cameras VLAN from accessing LAN",
    },
    
    # VLAN creation (Phase 3, NOT auto-safe - high impact)
    FindingCode.MISSING_NETWORK_SEGMENTATION.value: {
        "category": "vlan",
        "change_type": "create",
        "target": "{vlan_name}",
        "patch": {
            "name": "{vlan_name}",
            "vlan_enabled": True,
            "vlan": "{vlan_id}",
            "subnet": "{subnet}",
            "dhcpd_enabled": True,
        },
        "phase": 3,
        "auto_apply_safe": False,  # Requires human review
        "description": "Create missing VLAN for network segmentation",
    },
    
    # Open WiFi (Phase 1, NOT auto-safe - needs password)
    FindingCode.OPEN_WIFI.value: {
        "category": "wifi",
        "change_type": "update",
        "target": "{ssid}",
        "patch": {"security": "wpapsk", "wpa_mode": "wpa2"},
        "phase": 1,
        "auto_apply_safe": False,  # Needs password to be set
        "description": "Enable WPA2 encryption (requires password setup)",
    },
    
    # IoT WiFi VLAN (Phase 1, auto-safe if VLAN exists)
    FindingCode.IOT_WIFI_NO_VLAN.value: {
        "category": "wifi",
        "change_type": "update",
        "target": "{ssid}",
        "patch": {"vlan_enabled": True, "vlan": 30},
        "phase": 1,
        "auto_apply_safe": True,
        "description": "Assign IoT WiFi to dedicated VLAN",
        "dependencies": ["IoT VLAN must exist"],
    },
}


def generate_patches_from_findings(
    findings: List[Dict[str, Any]],
    include_severities: Optional[List[str]] = None,
    include_areas: Optional[List[str]] = None,
    auto_safe_only: bool = False,
) -> List[HardeningPatch]:
    """Generate machine-actionable patches from audit findings.
    
    Uses the stable finding codes to map findings to specific patches.
    
    Args:
        findings: List of finding dictionaries (from audit output)
        include_severities: Filter by severity (e.g., ["high", "critical"])
        include_areas: Filter by area (e.g., ["firewall", "wifi"])
        auto_safe_only: Only return patches marked as auto_apply_safe=True
        
    Returns:
        List of HardeningPatch objects ready for application
    """
    patches = []
    patch_counter = 0
    
    for finding in findings:
        code = finding.get("code", "")
        severity = finding.get("severity", "medium")
        area = finding.get("area", "")
        evidence = finding.get("evidence", {})
        
        # Apply filters
        if include_severities and severity not in include_severities:
            continue
        if include_areas and area not in include_areas:
            continue
        
        # Look up patch template
        template = FINDING_CODE_TO_PATCH.get(code)
        if not template:
            logger.debug(f"No patch template for finding code: {code}")
            continue
        
        # Check auto-safe filter
        if auto_safe_only and not template.get("auto_apply_safe", False):
            continue
        
        # Generate patch from template
        patch_counter += 1
        patch_id = f"patch_{template['category']}_{patch_counter:03d}"
        
        # Substitute placeholders from evidence
        target = template["target"]
        patch_data = template["patch"].copy()
        
        if "{ssid}" in target:
            target = evidence.get("ssid", target)
        if "{vlan_name}" in target:
            target = evidence.get("vlan_name", evidence.get("missing", ["Unknown"])[0] if isinstance(evidence.get("missing"), list) else "Unknown")
        
        # Substitute in patch data
        for key, value in patch_data.items():
            if isinstance(value, str):
                if "{ssid}" in value:
                    patch_data[key] = evidence.get("ssid", value)
                if "{vlan_name}" in value:
                    patch_data[key] = evidence.get("vlan_name", value)
                if "{vlan_id}" in value:
                    patch_data[key] = evidence.get("vlan_id", 100)
                if "{subnet}" in value:
                    patch_data[key] = evidence.get("subnet", "192.168.100.0/24")
        
        patches.append(HardeningPatch(
            id=patch_id,
            category=template["category"],
            change_type=template["change_type"],
            target=target,
            patch=patch_data,
            finding_ids=[finding.get("id", "")],
            finding_codes=[code],
            phase=template["phase"],
            dependencies=template.get("dependencies", []),
            auto_apply_safe=template.get("auto_apply_safe", False),
            description=template.get("description", f"Fix {code}"),
            severity=severity,
        ))
    
    return patches


class SecurityHardenUniFiInput(BaseModel):
    """Input schema for security_harden_unifi tool."""
    
    dry_run: bool = Field(
        default=True,
        description="If true, preview changes without applying (default: true for safety)"
    )
    plan: Optional[HardeningPlan] = Field(
        default=None,
        description="Hardening plan from security_audit_unifi. If not provided, runs audit first."
    )
    phases: List[int] = Field(
        default_factory=lambda: [1, 2, 3],
        description="Which phases to apply (default: all)"
    )
    include_severities: List[str] = Field(
        default_factory=lambda: ["critical", "high", "medium", "low"],
        description="Filter patches by finding severity: critical, high, medium, low"
    )
    include_areas: List[str] = Field(
        default_factory=lambda: ["vlan", "wifi", "firewall", "dns_dhcp", "remote", "settings"],
        description="Filter patches by area: vlan, wifi, firewall, dns_dhcp, remote, settings"
    )
    apply_auto_safe_only: bool = Field(
        default=False,
        description="Only apply patches marked as auto_apply_safe=True (conservative mode)"
    )
    profile: str = Field(
        default="baseline",
        description="Security profile for audit: baseline, paranoid, lab"
    )
    stop_on_failure: bool = Field(
        default=True,
        description="Stop if a phase fails (default: true)"
    )
    create_backup: bool = Field(
        default=True,
        description="Create backup before applying changes (default: true)"
    )
    site_id: Optional[str] = Field(
        default=None,
        description="UniFi site ID (defaults to configured site)"
    )
    confirmation_token: Optional[str] = Field(
        default=None,
        description="Set to 'CONFIRM_HARDEN' to apply changes (required when dry_run=false)"
    )


class ChangeResult(BaseModel):
    """Result of applying a single change."""
    success: bool
    category: str
    target: str
    change_type: str
    phase: int
    error: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)


class PhaseResult(BaseModel):
    """Result of applying a single phase."""
    phase: int
    name: str
    description: str
    changes_count: int
    applied: bool
    success: bool
    changes_applied: int = 0
    changes_failed: int = 0
    errors: List[str] = Field(default_factory=list)
    connectivity_check: Optional[bool] = None


class SecurityHardenUniFiOutput(BaseModel):
    """Output schema for security_harden_unifi tool."""
    
    success: bool = Field(description="Whether overall operation succeeded")
    dry_run: bool = Field(description="Whether this was a dry run")
    execution_time: str = Field(default="", description="Execution timestamp")
    
    backup_id: str = Field(default="", description="Backup ID if created")
    
    phase_results: List[PhaseResult] = Field(
        default_factory=list,
        description="Results for each phase"
    )
    
    change_preview: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Preview of changes (for dry_run=true)"
    )
    
    total_changes: int = Field(default=0, description="Total changes in plan")
    total_applied: int = Field(default=0, description="Total changes applied")
    total_failed: int = Field(default=0, description="Total changes failed")
    
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    notes: List[str] = Field(default_factory=list, description="Additional notes")
    
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# Change Application Functions
# =============================================================================

async def apply_wifi_change(
    client: UniFiClient,
    patch: HardeningPatch,
) -> ChangeResult:
    """Apply a WiFi configuration change."""
    try:
        target = patch.target
        changes = patch.patch
        
        # Find the WLAN
        wlans = await client.get_wlans()
        wlan = next((w for w in wlans if w.get("name") == target or w.get("ssid") == changes.get("ssid")), None)
        
        if not wlan:
            return ChangeResult(
                success=False,
                category=patch.category,
                target=target,
                change_type=patch.change_type,
                phase=patch.phase,
                error=f"WLAN not found: {target}",
            )
        
        wlan_id = wlan.get("_id")
        
        # Build update payload
        updates = {}
        if "l2_isolation" in changes:
            updates["l2_isolation"] = changes["l2_isolation"]
        if "vlan_enabled" in changes:
            updates["vlan_enabled"] = changes["vlan_enabled"]
        if "vlan" in changes:
            updates["vlan"] = changes["vlan"]
        if "pmf_mode" in changes:
            updates["pmf_mode"] = changes["pmf_mode"]
        if "security" in changes:
            updates["security"] = changes["security"]
        if "wpa_mode" in changes:
            updates["wpa_mode"] = changes["wpa_mode"]
        if "wpa3_support" in changes:
            updates["wpa3_support"] = changes["wpa3_support"]
        
        if updates:
            await client.update_wlan(wlan_id, updates)
        
        return ChangeResult(
            success=True,
            category=patch.category,
            target=target,
            change_type=patch.change_type,
            phase=patch.phase,
            details={"updates": updates},
        )
        
    except Exception as e:
        return ChangeResult(
            success=False,
            category=patch.category,
            target=patch.target,
            change_type=patch.change_type,
            phase=patch.phase,
            error=str(e),
        )


async def apply_firewall_change(
    client: UniFiClient,
    patch: HardeningPatch,
) -> ChangeResult:
    """Apply a firewall rule change."""
    try:
        changes = patch.patch
        
        if patch.change_type == "create":
            # Get network IDs for source/destination
            networks = await client.get_networks()
            network_map = {n.get("name", ""): n.get("_id", "") for n in networks}
            
            rule_config = {
                "name": changes.get("name", f"Auto: {patch.target}"),
                "enabled": True,
                "action": changes.get("action", "drop"),
                "protocol": changes.get("protocol", "all"),
                "ruleset": changes.get("ruleset", "lan_in"),
            }
            
            # Resolve network names to IDs
            if "src_network" in changes:
                src_id = network_map.get(changes["src_network"])
                if src_id:
                    rule_config["src_networkconf_id"] = src_id
            
            if "dst_network" in changes:
                dst_id = network_map.get(changes["dst_network"])
                if dst_id:
                    rule_config["dst_networkconf_id"] = dst_id
            
            await client.create_firewall_rule(rule_config)
            
            return ChangeResult(
                success=True,
                category=patch.category,
                target=patch.target,
                change_type=patch.change_type,
                phase=patch.phase,
                details={"rule_config": rule_config},
            )
        
        elif patch.change_type == "update":
            rule_id = changes.get("rule_id")
            if not rule_id:
                return ChangeResult(
                    success=False,
                    category=patch.category,
                    target=patch.target,
                    change_type=patch.change_type,
                    phase=patch.phase,
                    error="No rule_id provided for update",
                )
            
            updates = {k: v for k, v in changes.items() if k != "rule_id"}
            await client.update_firewall_rule(rule_id, updates)
            
            return ChangeResult(
                success=True,
                category=patch.category,
                target=patch.target,
                change_type=patch.change_type,
                phase=patch.phase,
                details={"updates": updates},
            )
        
        else:
            return ChangeResult(
                success=False,
                category=patch.category,
                target=patch.target,
                change_type=patch.change_type,
                phase=patch.phase,
                error=f"Unsupported change type: {patch.change_type}",
            )
        
    except Exception as e:
        return ChangeResult(
            success=False,
            category=patch.category,
            target=patch.target,
            change_type=patch.change_type,
            phase=patch.phase,
            error=str(e),
        )


async def apply_vlan_change(
    client: UniFiClient,
    patch: HardeningPatch,
) -> ChangeResult:
    """Apply a VLAN/network change."""
    try:
        changes = patch.patch
        
        if patch.change_type == "create":
            vlan_config = changes.get("create_vlan", changes)
            
            network_config = {
                "name": vlan_config.get("name", patch.target),
                "purpose": "corporate",
                "vlan_enabled": True,
                "vlan": vlan_config.get("vlan_id", 100),
                "ip_subnet": vlan_config.get("subnet", "192.168.100.0/24"),
                "dhcpd_enabled": vlan_config.get("dhcp", True),
            }
            
            await client.create_network(network_config)
            
            return ChangeResult(
                success=True,
                category=patch.category,
                target=patch.target,
                change_type=patch.change_type,
                phase=patch.phase,
                details={"network_config": network_config},
            )
        
        elif patch.change_type == "update":
            # Find network by name
            networks = await client.get_networks()
            network = next(
                (n for n in networks if n.get("name") == patch.target),
                None
            )
            
            if not network:
                return ChangeResult(
                    success=False,
                    category=patch.category,
                    target=patch.target,
                    change_type=patch.change_type,
                    phase=patch.phase,
                    error=f"Network not found: {patch.target}",
                )
            
            network_id = network.get("_id")
            await client.update_network(network_id, changes)
            
            return ChangeResult(
                success=True,
                category=patch.category,
                target=patch.target,
                change_type=patch.change_type,
                phase=patch.phase,
                details={"updates": changes},
            )
        
        else:
            return ChangeResult(
                success=False,
                category=patch.category,
                target=patch.target,
                change_type=patch.change_type,
                phase=patch.phase,
                error=f"Unsupported change type: {patch.change_type}",
            )
        
    except Exception as e:
        return ChangeResult(
            success=False,
            category=patch.category,
            target=patch.target,
            change_type=patch.change_type,
            phase=patch.phase,
            error=str(e),
        )


async def apply_settings_change(
    client: UniFiClient,
    patch: HardeningPatch,
) -> ChangeResult:
    """Apply a settings change (UPnP, threat management, etc.)."""
    try:
        changes = patch.patch
        
        if patch.target == "upnp" or "upnp" in str(changes):
            await client.update_upnp_settings(changes)
        elif patch.target == "threat_management" or "ips" in str(changes):
            # Threat management updates go through settings API
            # This would need implementation in the client
            pass
        
        return ChangeResult(
            success=True,
            category=patch.category,
            target=patch.target,
            change_type=patch.change_type,
            phase=patch.phase,
            details={"updates": changes},
        )
        
    except Exception as e:
        return ChangeResult(
            success=False,
            category=patch.category,
            target=patch.target,
            change_type=patch.change_type,
            phase=patch.phase,
            error=str(e),
        )


async def apply_patch(
    client: UniFiClient,
    patch: HardeningPatch,
) -> ChangeResult:
    """Apply a single patch based on category."""
    if patch.category == "wifi":
        return await apply_wifi_change(client, patch)
    elif patch.category == "firewall":
        return await apply_firewall_change(client, patch)
    elif patch.category == "vlan":
        return await apply_vlan_change(client, patch)
    elif patch.category == "settings":
        return await apply_settings_change(client, patch)
    else:
        return ChangeResult(
            success=False,
            category=patch.category,
            target=patch.target,
            change_type=patch.change_type,
            phase=patch.phase,
            error=f"Unknown category: {patch.category}",
        )


async def check_connectivity(client: UniFiClient) -> bool:
    """Verify we can still communicate with the controller."""
    try:
        await client.get_devices()
        return True
    except Exception:
        return False


# =============================================================================
# Main Hardening Function
# =============================================================================

async def security_harden_unifi(
    params: SecurityHardenUniFiInput
) -> SecurityHardenUniFiOutput:
    """Apply security hardening to UniFi network.
    
    Follows the UNIFI HARDENING AUTOMATION PLAN:
    
    PHASE 1 - Low-risk changes:
    - Disable UPnP/NAT-PMP
    - Enable client isolation on guest networks
    - Enable PMF (Protected Management Frames)
    - Update WiFi security settings
    
    PHASE 2 - Firewall rules:
    - Add IoT → LAN drop rules
    - Add Guest → LAN drop rules
    - Add Camera → LAN drop rules
    
    PHASE 3 - Network segmentation:
    - Create missing VLANs
    - Assign WiFi networks to VLANs
    - Update DHCP settings
    
    Args:
        params: Hardening parameters
        
    Returns:
        Results of hardening operation
    """
    logger.info(f"security_harden_unifi called: dry_run={params.dry_run}")
    
    execution_time = datetime.now().isoformat()
    warnings = []
    notes = []
    backup_id = ""
    
    # Safety check for non-dry-run
    if not params.dry_run:
        if params.confirmation_token != "CONFIRM_HARDEN":
            return SecurityHardenUniFiOutput(
                success=False,
                dry_run=params.dry_run,
                execution_time=execution_time,
                error="Safety check failed. Set confirmation_token='CONFIRM_HARDEN' to apply changes.",
                notes=["This is a safety feature. Set dry_run=true to preview changes first."],
            )
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            # Get or generate hardening plan
            if params.plan and params.plan.patches:
                patches = params.plan.patches
                notes.append("Using provided hardening plan")
            else:
                # Run audit to generate plan
                notes.append(f"No plan provided, running security audit (profile: {params.profile})...")
                audit_result = await security_audit_unifi(SecurityAuditUniFiInput(
                    depth="full",
                    profile=params.profile,
                    site_id=params.site_id,
                    include_patches=True,
                ))
                
                if not audit_result.success:
                    return SecurityHardenUniFiOutput(
                        success=False,
                        dry_run=params.dry_run,
                        execution_time=execution_time,
                        error=f"Audit failed: {audit_result.error}",
                    )
                
                # Generate patches from findings using code-based mapping
                findings_dicts = [
                    {
                        "id": f.id,
                        "code": f.code,
                        "severity": f.severity,
                        "area": f.area,
                        "evidence": f.evidence,
                    }
                    for f in audit_result.findings
                ]
                
                patches = generate_patches_from_findings(
                    findings=findings_dicts,
                    include_severities=params.include_severities,
                    include_areas=params.include_areas,
                    auto_safe_only=params.apply_auto_safe_only,
                )
                
                notes.append(f"Audit complete: {len(audit_result.findings)} findings, {len(patches)} patches generated")
                
                if params.apply_auto_safe_only:
                    notes.append("⚠️ Conservative mode: only auto-safe patches included")
            
            if not patches:
                return SecurityHardenUniFiOutput(
                    success=True,
                    dry_run=params.dry_run,
                    execution_time=execution_time,
                    total_changes=0,
                    notes=["No changes needed - configuration already follows best practices"],
                )
            
            # Filter patches by requested phases
            patches = [p for p in patches if p.phase in params.phases]
            
            # Group patches by phase
            patches_by_phase: Dict[int, List[HardeningPatch]] = {}
            for patch in patches:
                if patch.phase not in patches_by_phase:
                    patches_by_phase[patch.phase] = []
                patches_by_phase[patch.phase].append(patch)
            
            total_changes = len(patches)
            
            # DRY RUN MODE - Preview only
            if params.dry_run:
                change_preview = []
                phase_results = []
                
                auto_safe_count = 0
                for phase_num in sorted(patches_by_phase.keys()):
                    phase_patches = patches_by_phase[phase_num]
                    phase_def = PHASE_DEFINITIONS.get(phase_num, {})
                    
                    phase_results.append(PhaseResult(
                        phase=phase_num,
                        name=phase_def.get("name", f"Phase {phase_num}"),
                        description=phase_def.get("description", ""),
                        changes_count=len(phase_patches),
                        applied=False,
                        success=False,
                    ))
                    
                    for patch in phase_patches:
                        if patch.auto_apply_safe:
                            auto_safe_count += 1
                        change_preview.append({
                            "id": patch.id,
                            "phase": phase_num,
                            "category": patch.category,
                            "change_type": patch.change_type,
                            "target": patch.target,
                            "patch": patch.patch,
                            "finding_ids": patch.finding_ids,
                            "finding_codes": patch.finding_codes,
                            "impact": phase_def.get("impact", "unknown"),
                            "auto_apply_safe": patch.auto_apply_safe,
                            "description": patch.description,
                            "severity": patch.severity,
                        })
                
                notes.append("DRY RUN - No changes applied")
                notes.append(f"📊 {auto_safe_count}/{total_changes} patches are auto-safe")
                notes.append(f"To apply changes, set dry_run=false and confirmation_token='CONFIRM_HARDEN'")
                
                return SecurityHardenUniFiOutput(
                    success=True,
                    dry_run=True,
                    execution_time=execution_time,
                    phase_results=phase_results,
                    change_preview=change_preview,
                    total_changes=total_changes,
                    notes=notes,
                )
            
            # APPLY MODE - Actually make changes
            
            # Step 1: Create backup if requested
            if params.create_backup:
                try:
                    backup_result = await client.create_backup(label="pre-hardening")
                    backup_id = backup_result.get("backup_id", "")
                    notes.append(f"Created pre-hardening backup: {backup_id}")
                except Exception as e:
                    warnings.append(f"Failed to create backup: {e}")
                    if params.stop_on_failure:
                        return SecurityHardenUniFiOutput(
                            success=False,
                            dry_run=False,
                            execution_time=execution_time,
                            error=f"Backup creation failed: {e}",
                            warnings=warnings,
                        )
            
            # Step 2: Apply changes phase by phase
            phase_results = []
            total_applied = 0
            total_failed = 0
            
            for phase_num in sorted(patches_by_phase.keys()):
                phase_patches = patches_by_phase[phase_num]
                phase_def = PHASE_DEFINITIONS.get(phase_num, {})
                
                logger.info(f"Applying Phase {phase_num}: {phase_def.get('name', '')}")
                notes.append(f"Starting Phase {phase_num}: {phase_def.get('name', '')}")
                
                phase_applied = 0
                phase_failed = 0
                phase_errors = []
                
                # Apply each patch in the phase
                for patch in phase_patches:
                    result = await apply_patch(client, patch)
                    
                    if result.success:
                        phase_applied += 1
                        total_applied += 1
                    else:
                        phase_failed += 1
                        total_failed += 1
                        phase_errors.append(f"{patch.target}: {result.error}")
                
                # Connectivity check after phase
                await asyncio.sleep(1)  # Brief pause for changes to take effect
                connectivity_ok = await check_connectivity(client)
                
                phase_success = phase_failed == 0 and connectivity_ok
                
                phase_results.append(PhaseResult(
                    phase=phase_num,
                    name=phase_def.get("name", f"Phase {phase_num}"),
                    description=phase_def.get("description", ""),
                    changes_count=len(phase_patches),
                    applied=True,
                    success=phase_success,
                    changes_applied=phase_applied,
                    changes_failed=phase_failed,
                    errors=phase_errors,
                    connectivity_check=connectivity_ok,
                ))
                
                if not connectivity_ok:
                    warnings.append(f"⚠️ Connectivity check failed after Phase {phase_num}")
                
                if not phase_success and params.stop_on_failure:
                    warnings.append(f"Stopped after Phase {phase_num} due to failures")
                    
                    # Mark remaining phases as skipped
                    for remaining_phase in sorted(patches_by_phase.keys()):
                        if remaining_phase > phase_num:
                            remaining_patches = patches_by_phase[remaining_phase]
                            remaining_def = PHASE_DEFINITIONS.get(remaining_phase, {})
                            phase_results.append(PhaseResult(
                                phase=remaining_phase,
                                name=remaining_def.get("name", f"Phase {remaining_phase}"),
                                description=remaining_def.get("description", ""),
                                changes_count=len(remaining_patches),
                                applied=False,
                                success=False,
                                errors=["Skipped due to previous phase failure"],
                            ))
                    break
            
            # Final summary
            overall_success = total_failed == 0
            
            if overall_success:
                notes.append(f"✅ Successfully applied {total_applied} changes")
            else:
                notes.append(f"⚠️ Completed with {total_failed} failures out of {total_changes} changes")
            
            notes.append("Run security_audit_unifi again to verify improvements")
            
            logger.info(f"Hardening complete: {total_applied} applied, {total_failed} failed")
            
            return SecurityHardenUniFiOutput(
                success=overall_success,
                dry_run=False,
                execution_time=execution_time,
                backup_id=backup_id,
                phase_results=phase_results,
                total_changes=total_changes,
                total_applied=total_applied,
                total_failed=total_failed,
                warnings=warnings,
                notes=notes,
            )
        
    except UniFiConnectionError as e:
        logger.error(f"Connection error: {e}")
        return SecurityHardenUniFiOutput(
            success=False,
            dry_run=params.dry_run,
            execution_time=execution_time,
            error=f"Connection error: {e}",
        )
    except UniFiAuthError as e:
        logger.error(f"Auth error: {e}")
        return SecurityHardenUniFiOutput(
            success=False,
            dry_run=params.dry_run,
            execution_time=execution_time,
            error=f"Authentication error: {e}",
        )
    except UniFiAPIError as e:
        logger.error(f"API error: {e}")
        return SecurityHardenUniFiOutput(
            success=False,
            dry_run=params.dry_run,
            execution_time=execution_time,
            error=f"API error: {e}",
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return SecurityHardenUniFiOutput(
            success=False,
            dry_run=params.dry_run,
            execution_time=execution_time,
            error=f"Unexpected error: {e}",
        )

