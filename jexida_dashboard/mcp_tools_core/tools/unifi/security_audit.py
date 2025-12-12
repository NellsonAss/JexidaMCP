"""UniFi Comprehensive Security Audit Tool.

Provides the security_audit_unifi tool that evaluates UniFi configuration
against the complete hardening checklist (9 sections) and generates
findings, risk scores, and remediation patches.

Key features:
- Stable finding codes for machine-actionable mapping
- Risk scoring on 0-100 scale with letter grades
- Policy profiles (baseline, paranoid, lab)
- auto_apply_safe flags for safe vs risky changes
- Network summary with VLAN/SSID counts

Covers:
- Section 1: VLAN & Network Architecture
- Section 2: WiFi Hardening
- Section 3: Firewall Hardening
- Section 4: Threat Management (IDS/IPS)
- Section 5: DNS/DHCP Protection
- Section 6: Switch, PoE, & AP Hardening
- Section 7: Remote Access & Admin Hardening
- Section 8: Backups & Drift Protection
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError

import logging
logger = logging.getLogger(__name__)


# =============================================================================
# Finding Codes (Stable identifiers for machine-actionable mapping)
# =============================================================================

class FindingCode(str, Enum):
    """Stable finding codes for mapping to patches."""
    # VLAN Architecture (Section 1)
    MISSING_NETWORK_SEGMENTATION = "MISSING_NETWORK_SEGMENTATION"
    GUEST_NOT_ISOLATED = "GUEST_NOT_ISOLATED"
    IOT_CAN_REACH_LAN = "IOT_CAN_REACH_LAN"
    GUEST_CAN_REACH_LAN = "GUEST_CAN_REACH_LAN"
    CAMERAS_CAN_REACH_LAN = "CAMERAS_CAN_REACH_LAN"
    
    # WiFi (Section 2)
    OPEN_WIFI = "OPEN_WIFI"
    NO_WPA3 = "NO_WPA3"
    NO_PMF = "NO_PMF"
    IOT_WIFI_NO_VLAN = "IOT_WIFI_NO_VLAN"
    WEAK_WIFI_SECURITY = "WEAK_WIFI_SECURITY"
    GUEST_NO_CLIENT_ISOLATION = "GUEST_NO_CLIENT_ISOLATION"
    
    # Firewall (Section 3)
    MISSING_DENY_IOT_TO_LAN = "MISSING_DENY_IOT_TO_LAN"
    MISSING_DENY_GUEST_TO_LAN = "MISSING_DENY_GUEST_TO_LAN"
    MISSING_DENY_CAMERAS_TO_LAN = "MISSING_DENY_CAMERAS_TO_LAN"
    OVERLY_PERMISSIVE_RULE = "OVERLY_PERMISSIVE_RULE"
    SHADOWED_RULE = "SHADOWED_RULE"
    
    # Threat Management (Section 4)
    IDS_DISABLED = "IDS_DISABLED"
    IPS_NOT_ENABLED = "IPS_NOT_ENABLED"
    THREAT_CATEGORIES_MISSING = "THREAT_CATEGORIES_MISSING"
    
    # DNS/DHCP (Section 5)
    UPNP_ENABLED = "UPNP_ENABLED"
    NAT_PMP_ENABLED = "NAT_PMP_ENABLED"
    UNTRUSTED_DNS = "UNTRUSTED_DNS"
    WIDE_DHCP_RANGE = "WIDE_DHCP_RANGE"
    
    # Switch/AP (Section 6)
    UNUSED_PORT_ENABLED = "UNUSED_PORT_ENABLED"
    POE_MISCONFIGURED = "POE_MISCONFIGURED"
    CHANNEL_OVERLAP = "CHANNEL_OVERLAP"
    
    # Remote Access (Section 7)
    SSH_ENABLED = "SSH_ENABLED"
    SSH_PASSWORD_AUTH = "SSH_PASSWORD_AUTH"
    CLOUD_ACCESS_ENABLED = "CLOUD_ACCESS_ENABLED"
    WAN_UI_ENABLED = "WAN_UI_ENABLED"
    NO_MFA = "NO_MFA"
    
    # Backups (Section 8)
    NO_RECENT_BACKUP = "NO_RECENT_BACKUP"
    CONFIG_DRIFT = "CONFIG_DRIFT"


# =============================================================================
# Policy Profiles
# =============================================================================

POLICY_PROFILES = {
    "baseline": {
        "name": "Baseline",
        "description": "Balanced security suitable for most home/small office networks",
        "overrides": {
            "section_7_remote_access": {
                "disable_cloud_access": {"enabled": False},  # Allow cloud access
            },
            "section_4_threat_management": {
                "block_tor_proxy_vpn": {"enabled": False},
            },
        },
        "severity_overrides": {
            FindingCode.CLOUD_ACCESS_ENABLED: "low",
            FindingCode.NO_WPA3: "low",
        },
        "auto_apply_safe_threshold": "high",  # Only auto-apply for high+ findings
    },
    "paranoid": {
        "name": "Paranoid",
        "description": "Maximum security for high-risk environments",
        "overrides": {
            "section_7_remote_access": {
                "disable_cloud_access": {"enabled": True, "severity": "high"},
                "require_mfa": {"enabled": True, "severity": "critical"},
            },
            "section_4_threat_management": {
                "block_tor_proxy_vpn": {"enabled": True, "severity": "high"},
            },
            "section_2_wifi": {
                "enforce_wpa3": {"enabled": True, "severity": "high"},
                "require_pmf": {"enabled": True, "severity": "high"},
            },
        },
        "severity_overrides": {
            FindingCode.NO_WPA3: "high",
            FindingCode.CLOUD_ACCESS_ENABLED: "high",
            FindingCode.SSH_ENABLED: "high",
        },
        "auto_apply_safe_threshold": "medium",  # More aggressive auto-apply
    },
    "lab": {
        "name": "Lab/Development",
        "description": "Minimal restrictions for development/testing environments",
        "overrides": {
            "section_5_dns_dhcp": {
                "disable_upnp": {"enabled": False},
            },
            "section_7_remote_access": {
                "disable_device_ssh": {"enabled": False},
            },
        },
        "severity_overrides": {
            FindingCode.UPNP_ENABLED: "low",
            FindingCode.SSH_ENABLED: "low",
            FindingCode.SSH_PASSWORD_AUTH: "low",
        },
        "auto_apply_safe_threshold": "critical",  # Only auto-apply critical
    },
}


# =============================================================================
# Severity and Finding Models
# =============================================================================

class Severity(str, Enum):
    """Finding severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Finding:
    """A security finding from the audit."""
    id: str
    code: FindingCode  # Stable code for machine-actionable mapping
    severity: Severity
    area: str  # Section/category area
    check_id: str  # Reference to checklist item (e.g., "WIFI-2.1")
    title: str
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    recommendation: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code.value,
            "severity": self.severity.value,
            "area": self.area,
            "check_id": self.check_id,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
        }


@dataclass
class RecommendedPatch:
    """A recommended configuration patch."""
    id: str  # Unique patch ID (e.g., "patch_disable_upnp")
    category: str
    change_type: str
    target: str
    patch: Dict[str, Any]
    finding_ids: List[str]
    finding_codes: List[str] = field(default_factory=list)  # Related finding codes
    phase: int = 1
    dependencies: List[str] = field(default_factory=list)
    auto_apply_safe: bool = True  # Whether patch is safe to auto-apply
    description: str = ""  # Human-readable description
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "change_type": self.change_type,
            "target": self.target,
            "patch": self.patch,
            "finding_ids": self.finding_ids,
            "finding_codes": self.finding_codes,
            "phase": self.phase,
            "dependencies": self.dependencies,
            "auto_apply_safe": self.auto_apply_safe,
            "description": self.description,
        }


# =============================================================================
# Policy Loader
# =============================================================================

def load_security_policy(
    policy_path: Optional[str] = None,
    profile: str = "baseline",
) -> Dict[str, Any]:
    """Load security policy from JSON file with optional profile overrides.
    
    Args:
        policy_path: Path to policy file (defaults to security_policy.json)
        profile: Policy profile to apply ("baseline", "paranoid", "lab")
        
    Returns:
        Parsed policy dictionary with profile overrides applied
    """
    if policy_path is None:
        base_dir = Path(__file__).parent
        policy_path = base_dir / "security_policy.json"
    else:
        policy_path = Path(policy_path)
    
    if not policy_path.exists():
        logger.warning(f"Policy file not found: {policy_path}")
        return {}
    
    with open(policy_path, "r") as f:
        policy = json.load(f)
    
    # Apply profile overrides
    profile_config = POLICY_PROFILES.get(profile, POLICY_PROFILES["baseline"])
    overrides = profile_config.get("overrides", {})
    
    for section_key, section_overrides in overrides.items():
        if section_key in policy:
            for check_key, check_overrides in section_overrides.items():
                if check_key in policy[section_key]:
                    policy[section_key][check_key].update(check_overrides)
    
    # Store profile metadata in policy
    policy["_profile"] = {
        "name": profile,
        "display_name": profile_config.get("name", profile),
        "description": profile_config.get("description", ""),
        "severity_overrides": {
            code.value if isinstance(code, FindingCode) else code: sev
            for code, sev in profile_config.get("severity_overrides", {}).items()
        },
        "auto_apply_safe_threshold": profile_config.get("auto_apply_safe_threshold", "high"),
    }
    
    return policy


def get_profile_severity(
    code: FindingCode,
    default_severity: Severity,
    policy: Dict[str, Any],
) -> Severity:
    """Get severity for a finding code, considering profile overrides.
    
    Args:
        code: Finding code
        default_severity: Default severity from policy
        policy: Policy dictionary with profile metadata
        
    Returns:
        Effective severity level
    """
    profile_meta = policy.get("_profile", {})
    severity_overrides = profile_meta.get("severity_overrides", {})
    
    override = severity_overrides.get(code.value)
    if override:
        return Severity(override)
    return default_severity


# =============================================================================
# Comprehensive Policy Evaluator
# =============================================================================

class ComprehensiveEvaluator:
    """Evaluates UniFi configuration against all 9 security sections."""
    
    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy
        self.findings: List[Finding] = []
        self.patches: List[RecommendedPatch] = []
        self._finding_counter = 0
        self._patch_counter = 0
        self._network_map: Dict[str, str] = {}  # name -> id
        self._vlan_map: Dict[str, int] = {}  # name -> vlan_id
        self._network_summary: Dict[str, Any] = {}  # Will be populated during evaluation
    
    def _next_finding_id(self) -> str:
        self._finding_counter += 1
        return f"F{self._finding_counter:03d}"
    
    def _next_patch_id(self, prefix: str) -> str:
        self._patch_counter += 1
        return f"patch_{prefix}_{self._patch_counter:03d}"
    
    def _add_finding(
        self,
        code: FindingCode,
        severity: Severity,
        area: str,
        check_id: str,
        title: str,
        description: str,
        evidence: Dict[str, Any] = None,
        patch: Dict[str, Any] = None,
        summary: str = "",
    ) -> str:
        """Add a finding and optionally a remediation patch.
        
        Args:
            code: Stable finding code for machine-actionable mapping
            severity: Finding severity (may be overridden by profile)
            area: Section/category area (vlan, wifi, firewall, etc.)
            check_id: Reference to checklist item (e.g., "WIFI-2.1")
            title: Human-readable title
            description: Detailed description
            evidence: Supporting evidence dictionary
            patch: Optional patch suggestion
            summary: Short summary of remediation
            
        Returns:
            Finding ID
        """
        finding_id = self._next_finding_id()
        
        # Apply profile severity overrides
        effective_severity = get_profile_severity(code, severity, self.policy)
        
        recommendation = {}
        if patch:
            recommendation["patch"] = patch
        if summary:
            recommendation["summary"] = summary
        
        self.findings.append(Finding(
            id=finding_id,
            code=code,
            severity=effective_severity,
            area=area,
            check_id=check_id,
            title=title,
            description=description,
            evidence=evidence or {},
            recommendation=recommendation,
        ))
        
        return finding_id
    
    def _add_patch(
        self,
        finding_id: str,
        finding_code: FindingCode,
        category: str,
        change_type: str,
        target: str,
        patch: Dict[str, Any],
        phase: int = 1,
        dependencies: List[str] = None,
        auto_apply_safe: bool = True,
        description: str = "",
    ) -> None:
        """Add a recommended patch.
        
        Args:
            finding_id: Related finding ID
            finding_code: Related finding code
            category: Change category (wifi, firewall, vlan, settings)
            change_type: Type of change (create, update, delete)
            target: Target name/ID
            patch: The patch data
            phase: Phase number (1=low-risk, 2=firewall, 3=vlan)
            dependencies: List of dependencies
            auto_apply_safe: Whether this is safe to auto-apply
            description: Human-readable description
        """
        patch_id = self._next_patch_id(category)
        
        self.patches.append(RecommendedPatch(
            id=patch_id,
            category=category,
            change_type=change_type,
            target=target,
            patch=patch,
            finding_ids=[finding_id],
            finding_codes=[finding_code.value],
            phase=phase,
            dependencies=dependencies or [],
            auto_apply_safe=auto_apply_safe,
            description=description or f"Fix {finding_code.value}",
        ))
    
    # =========================================================================
    # Section 1: VLAN & Network Architecture
    # =========================================================================
    
    def evaluate_vlan_architecture(
        self,
        networks: List[Dict[str, Any]],
        wifi_networks: List[Dict[str, Any]],
    ) -> None:
        """Evaluate VLAN and network architecture against policy."""
        policy_section = self.policy.get("section_1_vlan_architecture", {})
        
        # Build network maps and populate network summary
        vlan_count = 0
        for net in networks:
            name = net.get("name", "")
            self._network_map[name] = net.get("_id", "")
            if net.get("vlan_enabled") and net.get("vlan"):
                self._vlan_map[name] = int(net["vlan"])
                vlan_count += 1
        
        self._network_summary["total_networks"] = len(networks)
        self._network_summary["vlan_count"] = vlan_count
        self._network_summary["ssid_count"] = len([w for w in wifi_networks if w.get("enabled", False)])
        
        # 1.1 - Check for required segmentation
        seg_policy = policy_section.get("require_segmentation", {})
        if seg_policy.get("enabled", True):
            required_vlans = seg_policy.get("required_vlans", ["LAN", "IoT", "Guest"])
            network_names = [n.get("name", "").lower() for n in networks]
            
            missing_vlans = []
            for required in required_vlans:
                found = any(required.lower() in name for name in network_names)
                if not found:
                    missing_vlans.append(required)
            
            if missing_vlans:
                finding_id = self._add_finding(
                    code=FindingCode.MISSING_NETWORK_SEGMENTATION,
                    severity=Severity.HIGH,
                    area="vlan",
                    check_id="VLAN-1.1",
                    title="Missing network segmentation",
                    description=f"Required VLANs not found: {', '.join(missing_vlans)}. Flat networks = widest attack surface.",
                    evidence={"existing_networks": network_names, "missing": missing_vlans},
                    summary=f"Create VLANs for: {', '.join(missing_vlans)}",
                )
                
                # Generate patch for each missing VLAN
                for vlan_name in missing_vlans:
                    vlan_id = {"IoT": 30, "Guest": 40, "Cameras": 50, "Work": 60}.get(vlan_name, 100)
                    subnet = f"192.168.{vlan_id}.0/24"
                    
                    self._add_patch(
                        finding_id=finding_id,
                        finding_code=FindingCode.MISSING_NETWORK_SEGMENTATION,
                        category="vlan",
                        change_type="create",
                        target=vlan_name,
                        patch={
                            "create_vlan": {
                                "name": vlan_name,
                                "vlan_id": vlan_id,
                                "subnet": subnet,
                                "dhcp": True,
                            }
                        },
                        phase=3,  # VLAN changes are phase 3 (high impact)
                        auto_apply_safe=False,  # VLAN creation needs human review
                        description=f"Create {vlan_name} VLAN with ID {vlan_id}",
                    )
        
        # 1.3 - Guest network isolation
        guest_policy = policy_section.get("guest_network_isolation", {})
        if guest_policy.get("enabled", True):
            guest_wifis = [w for w in wifi_networks if w.get("is_guest", False) and w.get("enabled", False)]
            
            for guest_wifi in guest_wifis:
                ssid = guest_wifi.get("name", "Unknown")
                issues = []
                
                # Check client isolation
                if not guest_wifi.get("l2_isolation", False):
                    issues.append("client isolation disabled")
                
                # Check VLAN
                if not guest_wifi.get("vlan_enabled", False):
                    issues.append("not on separate VLAN")
                
                if issues:
                    finding_id = self._add_finding(
                        code=FindingCode.GUEST_NOT_ISOLATED,
                        severity=Severity.HIGH,
                        area="vlan",
                        check_id="VLAN-1.3",
                        title=f"Guest network not properly isolated: {ssid}",
                        description=f"Issues: {', '.join(issues)}. Guest isolation prevents lateral movement.",
                        evidence={"ssid": ssid, "issues": issues},
                        patch={
                            "wifi_update": {
                                "name": ssid,
                                "client_isolation": True,
                                "vlan_id": 40,
                            }
                        },
                        summary="Enable client isolation and assign to guest VLAN",
                    )
                    
                    self._add_patch(
                        finding_id=finding_id,
                        finding_code=FindingCode.GUEST_NOT_ISOLATED,
                        category="wifi",
                        change_type="update",
                        target=ssid,
                        patch={
                            "ssid": ssid,
                            "l2_isolation": True,
                            "vlan_enabled": True,
                            "vlan": 40,
                        },
                        phase=1,
                        auto_apply_safe=True,
                        description=f"Enable client isolation on guest network {ssid}",
                    )
    
    # =========================================================================
    # Section 2: WiFi Hardening
    # =========================================================================
    
    def evaluate_wifi(self, wifi_networks: List[Dict[str, Any]]) -> None:
        """Evaluate WiFi configuration against policy."""
        policy_section = self.policy.get("section_2_wifi", {})
        
        for network in wifi_networks:
            if not network.get("enabled", False):
                continue
            
            ssid = network.get("name", "Unknown")
            security = network.get("security", "open")
            wpa_mode = network.get("wpa_mode", "")
            wpa3_support = network.get("wpa3_support", False)
            pmf_mode = network.get("pmf_mode", "disabled")
            is_guest = network.get("is_guest", False)
            vlan_enabled = network.get("vlan_enabled", False)
            
            # 2.5 - Check for open (unencrypted) networks
            enc_policy = policy_section.get("require_encryption", {})
            if enc_policy.get("enabled", True):
                allowed_open = enc_policy.get("allowed_open_ssids", [])
                if security == "open" and ssid not in allowed_open:
                    finding_id = self._add_finding(
                        code=FindingCode.OPEN_WIFI,
                        severity=Severity.CRITICAL,
                        area="wifi",
                        check_id="WIFI-2.5",
                        title=f"Open WiFi network: {ssid}",
                        description="WiFi network has no encryption. All traffic can be intercepted.",
                        evidence={"ssid": ssid, "security": security},
                        patch={"wifi_update": {"name": ssid, "security": "WPA2"}},
                        summary="Enable WPA2 or WPA3 encryption",
                    )
                    
                    self._add_patch(
                        finding_id=finding_id,
                        finding_code=FindingCode.OPEN_WIFI,
                        category="wifi",
                        change_type="update",
                        target=ssid,
                        patch={"ssid": ssid, "security": "wpapsk", "wpa_mode": "wpa2"},
                        phase=1,
                        auto_apply_safe=False,  # Need password setup
                        description=f"Enable WPA2 encryption on {ssid}",
                    )
                    continue
            
            # 2.1 - WPA3 enforcement
            wpa3_policy = policy_section.get("enforce_wpa3", {})
            if wpa3_policy.get("enabled", True):
                if not wpa3_support and security != "open":
                    self._add_finding(
                        code=FindingCode.NO_WPA3,
                        severity=Severity.MEDIUM,
                        area="wifi",
                        check_id="WIFI-2.1",
                        title=f"WPA3 not enabled on {ssid}",
                        description="WPA3 provides stronger security. Consider enabling WPA3 transition mode.",
                        evidence={"ssid": ssid, "current_mode": wpa_mode},
                        patch={"wifi_update": {"name": ssid, "security": "WPA3"}},
                        summary="Enable WPA3 or WPA2-WPA3 transition mode",
                    )
            
            # 2.2 - PMF requirement
            pmf_policy = policy_section.get("require_pmf", {})
            if pmf_policy.get("enabled", True):
                if pmf_mode not in ("required", "optional"):
                    finding_id = self._add_finding(
                        code=FindingCode.NO_PMF,
                        severity=Severity.MEDIUM,
                        area="wifi",
                        check_id="WIFI-2.2",
                        title=f"PMF not enabled on {ssid}",
                        description="Protected Management Frames prevent deauth attacks.",
                        evidence={"ssid": ssid, "pmf_mode": pmf_mode},
                        patch={"wifi_update": {"name": ssid, "pmf_mode": "required"}},
                        summary="Enable Protected Management Frames",
                    )
                    
                    self._add_patch(
                        finding_id=finding_id,
                        finding_code=FindingCode.NO_PMF,
                        category="wifi",
                        change_type="update",
                        target=ssid,
                        patch={"ssid": ssid, "pmf_mode": "required"},
                        phase=1,
                        auto_apply_safe=True,
                        description=f"Enable PMF on {ssid}",
                    )
            
            # 2.4 - IoT WiFi VLAN check
            iot_policy = policy_section.get("iot_wifi_vlan", {})
            if iot_policy.get("enabled", True):
                iot_patterns = iot_policy.get("iot_ssid_patterns", ["IoT", "Smart", "Device"])
                is_iot_wifi = any(pattern.lower() in ssid.lower() for pattern in iot_patterns)
                
                if is_iot_wifi and not vlan_enabled:
                    finding_id = self._add_finding(
                        code=FindingCode.IOT_WIFI_NO_VLAN,
                        severity=Severity.MEDIUM,
                        area="wifi",
                        check_id="WIFI-2.4",
                        title=f"IoT WiFi not on dedicated VLAN: {ssid}",
                        description="IoT devices should be isolated on their own VLAN.",
                        evidence={"ssid": ssid, "vlan_enabled": vlan_enabled},
                        patch={"wifi_update": {"name": ssid, "vlan_id": 30}},
                        summary="Assign IoT SSID to dedicated VLAN",
                    )
                    
                    self._add_patch(
                        finding_id=finding_id,
                        finding_code=FindingCode.IOT_WIFI_NO_VLAN,
                        category="wifi",
                        change_type="update",
                        target=ssid,
                        patch={"ssid": ssid, "vlan_enabled": True, "vlan": 30},
                        phase=1,
                        dependencies=["IoT VLAN must exist"],
                        auto_apply_safe=True,
                        description=f"Assign {ssid} to IoT VLAN",
                    )
    
    # =========================================================================
    # Section 3: Firewall Hardening
    # =========================================================================
    
    def evaluate_firewall(
        self,
        firewall_rules: Dict[str, List[Dict[str, Any]]],
        networks: List[Dict[str, Any]],
    ) -> None:
        """Evaluate firewall rules against policy."""
        policy_section = self.policy.get("section_3_firewall", {})
        
        # Build network ID map
        network_id_to_name = {n.get("_id"): n.get("name", "") for n in networks}
        network_purposes = {n.get("name", ""): n.get("purpose", "") for n in networks}
        
        # Count firewall rules
        total_rules = sum(len(rules) for rules in firewall_rules.values())
        self._network_summary["firewall_rule_count"] = total_rules
        
        # 3.1 - Check for explicit deny rules for untrusted VLANs
        deny_policy = policy_section.get("explicit_deny_untrusted", {})
        if deny_policy.get("enabled", True):
            required_denies = deny_policy.get("required_denies", [
                {"from": "IoT", "to": "LAN"},
                {"from": "Guest", "to": "LAN"},
            ])
            
            # Collect all existing deny rules
            existing_denies = []
            for ruleset_name, rules in firewall_rules.items():
                for rule in rules:
                    if rule.get("action") == "drop" and rule.get("enabled", True):
                        src_id = rule.get("src_networkconf_id", "")
                        dst_id = rule.get("dst_networkconf_id", "")
                        src_name = network_id_to_name.get(src_id, "")
                        dst_name = network_id_to_name.get(dst_id, "")
                        if src_name and dst_name:
                            existing_denies.append({"from": src_name, "to": dst_name})
            
            # Check for missing deny rules
            for required in required_denies:
                from_net = required["from"]
                to_net = required["to"]
                
                found = any(
                    from_net.lower() in d["from"].lower() and to_net.lower() in d["to"].lower()
                    for d in existing_denies
                )
                
                if not found:
                    # Determine the specific finding code based on source
                    if "iot" in from_net.lower():
                        finding_code = FindingCode.MISSING_DENY_IOT_TO_LAN
                    elif "guest" in from_net.lower():
                        finding_code = FindingCode.MISSING_DENY_GUEST_TO_LAN
                    elif "camera" in from_net.lower():
                        finding_code = FindingCode.MISSING_DENY_CAMERAS_TO_LAN
                    else:
                        finding_code = FindingCode.IOT_CAN_REACH_LAN
                    
                    finding_id = self._add_finding(
                        code=finding_code,
                        severity=Severity.HIGH,
                        area="firewall",
                        check_id="FW-3.1",
                        title=f"Missing deny rule: {from_net} → {to_net}",
                        description=f"No explicit deny rule found blocking {from_net} access to {to_net}.",
                        evidence={"from": from_net, "to": to_net},
                        patch={
                            "firewall_rules": [{
                                "action": "drop",
                                "from": from_net,
                                "to": to_net,
                                "comment": f"Block {from_net} → {to_net}",
                            }]
                        },
                        summary=f"Add {from_net} → {to_net} drop rule",
                    )
                    
                    self._add_patch(
                        finding_id=finding_id,
                        finding_code=finding_code,
                        category="firewall",
                        change_type="create",
                        target=f"{from_net}_to_{to_net}_drop",
                        patch={
                            "name": f"Block {from_net} → {to_net}",
                            "action": "drop",
                            "ruleset": "lan_in",
                            "src_network": from_net,
                            "dst_network": to_net,
                            "protocol": "all",
                        },
                        phase=2,
                        auto_apply_safe=True,  # Deny rules are safe to add
                        description=f"Create firewall rule to block {from_net} → {to_net}",
                    )
        
        # 3.3/3.5 - Check for overly permissive rules
        allow_all_policy = policy_section.get("flag_allow_all_rules", {})
        if allow_all_policy.get("enabled", True):
            for ruleset_name, rules in firewall_rules.items():
                for rule in rules:
                    if not rule.get("enabled", True):
                        continue
                    
                    action = rule.get("action", "")
                    protocol = rule.get("protocol", "all")
                    dst_port = rule.get("dst_port", "")
                    rule_name = rule.get("name", "Unnamed")
                    
                    # Flag accept-all rules
                    if action == "accept" and protocol == "all" and not dst_port:
                        src = rule.get("src_address", "") or "any"
                        dst = rule.get("dst_address", "") or "any"
                        
                        if src == "any" or dst == "any":
                            self._add_finding(
                                code=FindingCode.OVERLY_PERMISSIVE_RULE,
                                severity=Severity.HIGH,
                                area="firewall",
                                check_id="FW-3.5",
                                title=f"Overly permissive rule: {rule_name}",
                                description=f"Rule in {ruleset_name} allows all traffic with no port restriction.",
                                evidence={
                                    "rule_name": rule_name,
                                    "ruleset": ruleset_name,
                                    "action": action,
                                    "protocol": protocol,
                                },
                                summary="Restrict by port/protocol or remove this rule",
                            )
    
    # =========================================================================
    # Section 4: Threat Management (IDS/IPS)
    # =========================================================================
    
    def evaluate_threat_management(self, threat_settings: Dict[str, Any]) -> None:
        """Evaluate IDS/IPS settings against policy."""
        policy_section = self.policy.get("section_4_threat_management", {})
        
        # Store threat management status in summary
        ips_enabled = threat_settings.get("ips_enabled", False)
        ips_mode = threat_settings.get("ips_mode", "disabled")
        self._network_summary["ids_ips_enabled"] = ips_enabled
        self._network_summary["ids_ips_mode"] = ips_mode
        
        ids_policy = policy_section.get("require_ids_ips", {})
        if ids_policy.get("enabled", True):
            recommended = ids_policy.get("recommended_mode", "ips")
            
            if not ips_enabled:
                finding_id = self._add_finding(
                    code=FindingCode.IDS_DISABLED,
                    severity=Severity.HIGH,
                    area="threat_management",
                    check_id="THREAT-4.1",
                    title="IDS/IPS is disabled",
                    description="Intrusion Detection/Prevention System provides critical network threat protection.",
                    evidence={"ips_enabled": ips_enabled, "mode": ips_mode},
                    patch={"settings_update": {"threat_mgmt": {"ips_enabled": True}}},
                    summary=f"Enable IDS/IPS in {recommended} mode",
                )
                
                self._add_patch(
                    finding_id=finding_id,
                    finding_code=FindingCode.IDS_DISABLED,
                    category="settings",
                    change_type="update",
                    target="threat_management",
                    patch={"ips_enabled": True, "ips_mode": recommended},
                    phase=1,
                    auto_apply_safe=True,
                    description=f"Enable IDS/IPS in {recommended} mode",
                )
            elif ips_mode == "ids" and recommended == "ips":
                self._add_finding(
                    code=FindingCode.IPS_NOT_ENABLED,
                    severity=Severity.LOW,
                    area="threat_management",
                    check_id="THREAT-4.1",
                    title="IDS mode only (IPS recommended)",
                    description="IPS mode actively blocks threats while IDS only detects them.",
                    evidence={"current_mode": ips_mode, "recommended": recommended},
                    summary="Consider switching from IDS to IPS mode",
                )
    
    # =========================================================================
    # Section 5: DNS/DHCP Protection
    # =========================================================================
    
    def evaluate_dns_dhcp(
        self,
        upnp_settings: Dict[str, Any],
        networks: List[Dict[str, Any]],
    ) -> None:
        """Evaluate DNS and DHCP settings against policy."""
        policy_section = self.policy.get("section_5_dns_dhcp", {})
        
        # Store UPnP status in summary
        self._network_summary["upnp_enabled"] = upnp_settings.get("upnp_enabled", False)
        self._network_summary["nat_pmp_enabled"] = upnp_settings.get("upnp_nat_pmp_enabled", False)
        
        # 5.3 - UPnP check
        upnp_policy = policy_section.get("disable_upnp", {})
        if upnp_policy.get("enabled", True):
            if upnp_settings.get("upnp_enabled", False):
                finding_id = self._add_finding(
                    code=FindingCode.UPNP_ENABLED,
                    severity=Severity.HIGH,
                    area="dns_dhcp",
                    check_id="DNS-5.3",
                    title="UPnP is enabled",
                    description="UPnP allows devices to automatically open ports, creating security risks.",
                    evidence={"upnp_enabled": True},
                    patch={"settings_update": {"upnp": {"enabled": False}}},
                    summary="Disable UPnP on the gateway",
                )
                
                self._add_patch(
                    finding_id=finding_id,
                    finding_code=FindingCode.UPNP_ENABLED,
                    category="settings",
                    change_type="update",
                    target="upnp",
                    patch={"upnp_enabled": False},
                    phase=1,
                    auto_apply_safe=True,
                    description="Disable UPnP",
                )
            
            if upnp_settings.get("upnp_nat_pmp_enabled", False):
                finding_id = self._add_finding(
                    code=FindingCode.NAT_PMP_ENABLED,
                    severity=Severity.HIGH,
                    area="dns_dhcp",
                    check_id="DNS-5.3",
                    title="NAT-PMP is enabled",
                    description="NAT-PMP allows automatic port mapping, similar security risk to UPnP.",
                    evidence={"upnp_nat_pmp_enabled": True},
                    patch={"settings_update": {"upnp": {"nat_pmp_enabled": False}}},
                    summary="Disable NAT-PMP",
                )
                
                self._add_patch(
                    finding_id=finding_id,
                    finding_code=FindingCode.NAT_PMP_ENABLED,
                    category="settings",
                    change_type="update",
                    target="upnp",
                    patch={"upnp_nat_pmp_enabled": False},
                    phase=1,
                    auto_apply_safe=True,
                    description="Disable NAT-PMP",
                )
    
    # =========================================================================
    # Section 6: Switch, PoE & AP Hardening
    # =========================================================================
    
    def evaluate_switch_ap(self, devices: List[Dict[str, Any]]) -> None:
        """Evaluate switch and AP configuration against policy."""
        policy_section = self.policy.get("section_6_switch_ap", {})
        
        # 6.1 - Check for unused ports
        unused_policy = policy_section.get("disable_unused_ports", {})
        if unused_policy.get("enabled", True):
            for device in devices:
                if device.get("type", "").startswith("usw"):  # Switch
                    ports = device.get("ports", [])
                    for port in ports:
                        if port.get("enable", True) and not port.get("up", False):
                            # Port is enabled but not connected - might be unused
                            # This is informational; we don't auto-disable without confirmation
                            pass  # Would need traffic history to determine truly unused
    
    # =========================================================================
    # Section 7: Remote Access & Admin Hardening
    # =========================================================================
    
    def evaluate_remote_access(self, mgmt_settings: Dict[str, Any]) -> None:
        """Evaluate remote access and admin settings against policy."""
        policy_section = self.policy.get("section_7_remote_access", {})
        
        # Store remote access status in summary
        self._network_summary["ssh_enabled"] = mgmt_settings.get("remote_access_enabled", False)
        self._network_summary["cloud_access_enabled"] = mgmt_settings.get("unifi_remote_access_enabled", False)
        
        # 7.2 - SSH on devices
        ssh_policy = policy_section.get("disable_device_ssh", {})
        if ssh_policy.get("enabled", True):
            if mgmt_settings.get("remote_access_enabled", False):
                self._add_finding(
                    code=FindingCode.SSH_ENABLED,
                    severity=Severity.MEDIUM,
                    area="remote_access",
                    check_id="REMOTE-7.2",
                    title="SSH enabled on devices",
                    description="SSH access to network devices should be disabled unless required for management.",
                    evidence={"ssh_enabled": True},
                    summary="Disable SSH on devices unless actively needed",
                )
        
        # 7.3 - Password auth
        if mgmt_settings.get("ssh_auth_password_enabled", False):
            self._add_finding(
                code=FindingCode.SSH_PASSWORD_AUTH,
                severity=Severity.MEDIUM,
                area="remote_access",
                check_id="REMOTE-7.2",
                title="SSH password authentication enabled",
                description="Password-based SSH is less secure than key-based authentication.",
                evidence={"password_auth": True},
                summary="Disable SSH password auth, use SSH keys instead",
            )
        
        # 7.4 - Cloud access
        cloud_policy = policy_section.get("disable_cloud_access", {})
        if cloud_policy.get("enabled", False):  # Disabled by default as many users want cloud
            if mgmt_settings.get("unifi_remote_access_enabled", False):
                self._add_finding(
                    code=FindingCode.CLOUD_ACCESS_ENABLED,
                    severity=Severity.LOW,
                    area="remote_access",
                    check_id="REMOTE-7.4",
                    title="UniFi cloud access enabled",
                    description="Cloud access allows remote management but increases attack surface.",
                    evidence={"cloud_access": True},
                    summary="Consider disabling cloud access if not needed",
                )
    
    # =========================================================================
    # Risk Score Calculation
    # =========================================================================
    
    def calculate_risk_score(self) -> Dict[str, Any]:
        """Calculate overall risk score on 0-100 scale with letter grades.
        
        Score interpretation:
        - 0-10: A+ (Excellent) - No significant issues
        - 11-25: A (Good) - Minor issues only
        - 26-40: B (Fair) - Some hardening recommended
        - 41-60: C (Needs Work) - Multiple issues to address
        - 61-80: D (Poor) - Significant security gaps
        - 81-100: F (Critical) - Major vulnerabilities
        
        Returns:
            Risk score dictionary with score, rating, letter grade, and breakdowns
        """
        scoring = self.policy.get("risk_scoring", {})
        
        # Weights for scoring (higher weight = more impact on score)
        weights = {
            Severity.CRITICAL: scoring.get("critical_weight", 15),
            Severity.HIGH: scoring.get("high_weight", 8),
            Severity.MEDIUM: scoring.get("medium_weight", 3),
            Severity.LOW: scoring.get("low_weight", 1),
        }
        
        # Maximum possible score (used for normalization)
        # Assume a "worst case" of ~10 findings per category max
        max_score = 100
        
        raw_score = 0
        by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_area = {}
        by_code = {}
        
        for finding in self.findings:
            raw_score += weights.get(finding.severity, 1)
            by_severity[finding.severity.value] += 1
            
            if finding.area not in by_area:
                by_area[finding.area] = 0
            by_area[finding.area] += 1
            
            code = finding.code.value
            if code not in by_code:
                by_code[code] = 0
            by_code[code] += 1
        
        # Normalize to 0-100 scale (cap at 100)
        normalized_score = min(raw_score, max_score)
        
        # Determine letter grade and rating
        if normalized_score <= 10:
            letter_grade = "A+"
            rating = "excellent"
        elif normalized_score <= 25:
            letter_grade = "A"
            rating = "good"
        elif normalized_score <= 40:
            letter_grade = "B"
            rating = "fair"
        elif normalized_score <= 60:
            letter_grade = "C"
            rating = "needs_work"
        elif normalized_score <= 80:
            letter_grade = "D"
            rating = "poor"
        else:
            letter_grade = "F"
            rating = "critical"
        
        return {
            "score": normalized_score,
            "raw_score": raw_score,
            "rating": rating,
            "letter_grade": letter_grade,
            "findings_by_severity": by_severity,
            "findings_by_area": by_area,
            "findings_by_code": by_code,
            "total_findings": len(self.findings),
        }
    
    def get_network_summary(self) -> Dict[str, Any]:
        """Get network summary statistics."""
        return self._network_summary
    
    def get_results(self) -> Tuple[List[Finding], List[RecommendedPatch], Dict[str, Any], Dict[str, Any]]:
        """Get evaluation results.
        
        Returns:
            Tuple of (findings, patches, risk_score, network_summary)
        """
        risk_score = self.calculate_risk_score()
        return self.findings, self.patches, risk_score, self._network_summary


# =============================================================================
# Input/Output Models
# =============================================================================

class SecurityAuditUniFiInput(BaseModel):
    """Input schema for security_audit_unifi tool."""
    
    depth: str = Field(
        default="full",
        description="Audit depth: 'quick' for essential checks only, 'full' for comprehensive audit"
    )
    profile: str = Field(
        default="baseline",
        description="Security profile: 'baseline' (balanced), 'paranoid' (maximum), 'lab' (minimal)"
    )
    site_id: Optional[str] = Field(
        default=None,
        description="UniFi site ID (defaults to configured site)"
    )
    policy_path: Optional[str] = Field(
        default=None,
        description="Path to custom security policy JSON file"
    )
    include_patches: bool = Field(
        default=True,
        description="Include recommended remediation patches in output"
    )


class FindingOutput(BaseModel):
    """A security finding in output format."""
    id: str
    code: str = Field(description="Stable finding code for machine-actionable mapping")
    severity: str
    area: str
    check_id: str
    title: str
    description: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    recommendation: Dict[str, Any] = Field(default_factory=dict)


class PatchOutput(BaseModel):
    """A recommended patch in output format."""
    id: str = Field(description="Unique patch identifier")
    category: str
    change_type: str
    target: str
    patch: Dict[str, Any]
    finding_ids: List[str]
    finding_codes: List[str] = Field(default_factory=list, description="Related finding codes")
    phase: int
    dependencies: List[str] = Field(default_factory=list)
    auto_apply_safe: bool = Field(default=True, description="Whether this patch is safe to auto-apply")
    description: str = Field(default="", description="Human-readable description")


class RiskScoreOutput(BaseModel):
    """Risk score summary on 0-100 scale."""
    score: int = Field(description="Risk score 0-100 (lower is better)")
    raw_score: int = Field(default=0, description="Raw weighted score before normalization")
    rating: str = Field(description="Rating: excellent, good, fair, needs_work, poor, critical")
    letter_grade: str = Field(default="", description="Letter grade: A+, A, B, C, D, F")
    findings_by_severity: Dict[str, int]
    findings_by_area: Dict[str, int]
    findings_by_code: Dict[str, int] = Field(default_factory=dict, description="Count by finding code")
    total_findings: int


class NetworkSummaryOutput(BaseModel):
    """Network summary statistics."""
    total_networks: int = Field(default=0, description="Total network count")
    vlan_count: int = Field(default=0, description="Number of VLANs")
    ssid_count: int = Field(default=0, description="Number of enabled SSIDs")
    firewall_rule_count: int = Field(default=0, description="Total firewall rules")
    ids_ips_enabled: bool = Field(default=False, description="Whether IDS/IPS is enabled")
    ids_ips_mode: str = Field(default="disabled", description="IDS/IPS mode")
    upnp_enabled: bool = Field(default=False, description="Whether UPnP is enabled")
    nat_pmp_enabled: bool = Field(default=False, description="Whether NAT-PMP is enabled")
    ssh_enabled: bool = Field(default=False, description="Whether SSH is enabled")
    cloud_access_enabled: bool = Field(default=False, description="Whether cloud access is enabled")


class SecurityAuditUniFiOutput(BaseModel):
    """Output schema for security_audit_unifi tool."""
    
    success: bool = Field(description="Whether the audit completed successfully")
    audit_time: str = Field(default="", description="Audit timestamp")
    depth: str = Field(default="full", description="Audit depth used")
    profile: str = Field(default="baseline", description="Security profile used")
    
    risk_score: Optional[RiskScoreOutput] = Field(
        default=None,
        description="Overall risk score (0-100) and rating"
    )
    
    network_summary: Optional[NetworkSummaryOutput] = Field(
        default=None,
        description="Network statistics summary"
    )
    
    findings: List[FindingOutput] = Field(
        default_factory=list,
        description="Security findings with severity levels and codes"
    )
    
    recommended_patches: List[PatchOutput] = Field(
        default_factory=list,
        description="Recommended configuration patches organized by phase"
    )
    
    sections_audited: List[str] = Field(
        default_factory=list,
        description="List of security sections that were evaluated"
    )
    
    notes: List[str] = Field(
        default_factory=list,
        description="Additional observations and notes"
    )
    
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# Main Audit Function
# =============================================================================

async def security_audit_unifi(
    params: SecurityAuditUniFiInput
) -> SecurityAuditUniFiOutput:
    """Perform a comprehensive security audit of UniFi network.
    
    Evaluates configuration against the complete hardening checklist:
    - Section 1: VLAN & Network Architecture
    - Section 2: WiFi Hardening
    - Section 3: Firewall Hardening
    - Section 4: Threat Management (IDS/IPS)
    - Section 5: DNS/DHCP Protection
    - Section 6: Switch, PoE, & AP Hardening
    - Section 7: Remote Access & Admin Hardening
    - Section 8: Backups & Drift Protection
    
    Features:
    - Stable finding codes for machine-actionable mapping
    - Risk scoring on 0-100 scale with letter grades
    - Policy profiles (baseline, paranoid, lab)
    - auto_apply_safe flags for safe vs risky changes
    - Network summary with VLAN/SSID counts
    
    Args:
        params: Audit parameters including depth, profile, and site_id
        
    Returns:
        Comprehensive audit results with findings, patches, and network summary
    """
    logger.info(f"security_audit_unifi called with depth={params.depth}, profile={params.profile}")
    
    audit_time = datetime.now().isoformat()
    notes = []
    sections_audited = []
    
    try:
        # Load policy with profile overrides
        policy = load_security_policy(params.policy_path, profile=params.profile)
        if not policy:
            notes.append("Using default security policy (custom policy not found)")
            policy = {}
        
        profile_info = policy.get("_profile", {})
        profile_name = profile_info.get("display_name", params.profile)
        notes.append(f"Using security profile: {profile_name}")
        
        evaluator = ComprehensiveEvaluator(policy)
        
        async with UniFiClient(site=params.site_id) as client:
            # Phase 1: Discovery - Gather all configuration
            wifi_networks = await client.get_wlans()
            networks = await client.get_networks()
            firewall_rules = await client.get_firewall_rules()
            upnp_settings = await client.get_upnp_settings()
            mgmt_settings = await client.get_mgmt_settings()
            threat_settings = await client.get_threat_management_settings()
            devices_detailed = await client.get_all_device_details()
            
            # Phase 2: Evaluation - Run all checks
            
            # Section 1: VLAN Architecture
            evaluator.evaluate_vlan_architecture(networks, wifi_networks)
            sections_audited.append("Section 1: VLAN & Network Architecture")
            
            # Section 2: WiFi
            evaluator.evaluate_wifi(wifi_networks)
            sections_audited.append("Section 2: WiFi Hardening")
            
            # Section 3: Firewall
            evaluator.evaluate_firewall(firewall_rules, networks)
            sections_audited.append("Section 3: Firewall Hardening")
            
            # Section 4: Threat Management
            evaluator.evaluate_threat_management(threat_settings)
            sections_audited.append("Section 4: Threat Management (IDS/IPS)")
            
            # Section 5: DNS/DHCP
            evaluator.evaluate_dns_dhcp(upnp_settings, networks)
            sections_audited.append("Section 5: DNS/DHCP Protection")
            
            # Section 6: Switch/AP (if full depth)
            if params.depth == "full":
                evaluator.evaluate_switch_ap(devices_detailed)
                sections_audited.append("Section 6: Switch, PoE, & AP Hardening")
            
            # Section 7: Remote Access
            evaluator.evaluate_remote_access(mgmt_settings)
            sections_audited.append("Section 7: Remote Access & Admin Hardening")
            
            # Section 8: Backups (checked via separate tool)
            sections_audited.append("Section 8: Backups & Drift (use drift_monitor tool)")
        
        # Get results
        findings, patches, risk_score, network_summary = evaluator.get_results()
        
        # Filter findings for quick mode
        if params.depth == "quick":
            findings = [f for f in findings if f.severity in (Severity.HIGH, Severity.CRITICAL)]
            notes.append("Quick mode: showing only high/critical findings")
        
        # Convert to output format
        findings_output = [
            FindingOutput(
                id=f.id,
                code=f.code.value,
                severity=f.severity.value,
                area=f.area,
                check_id=f.check_id,
                title=f.title,
                description=f.description,
                evidence=f.evidence,
                recommendation=f.recommendation,
            )
            for f in findings
        ]
        
        patches_output = []
        if params.include_patches:
            # Sort patches by phase
            patches_sorted = sorted(patches, key=lambda p: p.phase)
            patches_output = [
                PatchOutput(
                    id=p.id,
                    category=p.category,
                    change_type=p.change_type,
                    target=p.target,
                    patch=p.patch,
                    finding_ids=p.finding_ids,
                    finding_codes=p.finding_codes,
                    phase=p.phase,
                    dependencies=p.dependencies,
                    auto_apply_safe=p.auto_apply_safe,
                    description=p.description,
                )
                for p in patches_sorted
            ]
        
        risk_output = RiskScoreOutput(**risk_score)
        network_summary_output = NetworkSummaryOutput(**network_summary) if network_summary else None
        
        # Summary note
        if risk_score["total_findings"] == 0:
            notes.append("✅ Excellent! No security issues found - configuration follows best practices")
        else:
            critical_high = risk_score["findings_by_severity"]["critical"] + risk_score["findings_by_severity"]["high"]
            notes.append(
                f"Risk Score: {risk_score['score']}/100 ({risk_score['letter_grade']}) - "
                f"Found {risk_score['total_findings']} issue(s): "
                f"{risk_score['findings_by_severity']['critical']} critical, "
                f"{risk_score['findings_by_severity']['high']} high, "
                f"{risk_score['findings_by_severity']['medium']} medium, "
                f"{risk_score['findings_by_severity']['low']} low"
            )
            if critical_high > 0:
                notes.append(f"⚠️ {critical_high} critical/high severity issues require immediate attention")
            
            # Note auto-apply safe patches
            safe_patches = [p for p in patches if p.auto_apply_safe]
            if safe_patches:
                notes.append(f"💡 {len(safe_patches)} patches are safe for auto-apply")
        
        logger.info(f"Audit complete: {len(findings)} findings, risk score: {risk_score['score']} ({risk_score['letter_grade']})")
        
        return SecurityAuditUniFiOutput(
            success=True,
            audit_time=audit_time,
            depth=params.depth,
            profile=params.profile,
            risk_score=risk_output,
            network_summary=network_summary_output,
            findings=findings_output,
            recommended_patches=patches_output,
            sections_audited=sections_audited,
            notes=notes,
        )
        
    except UniFiConnectionError as e:
        logger.error(f"Connection error: {e}")
        return SecurityAuditUniFiOutput(
            success=False,
            audit_time=audit_time,
            error=f"Connection error: {e}",
        )
    except UniFiAuthError as e:
        logger.error(f"Auth error: {e}")
        return SecurityAuditUniFiOutput(
            success=False,
            audit_time=audit_time,
            error=f"Authentication error: {e}",
        )
    except UniFiAPIError as e:
        logger.error(f"API error: {e}")
        return SecurityAuditUniFiOutput(
            success=False,
            audit_time=audit_time,
            error=f"API error: {e}",
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return SecurityAuditUniFiOutput(
            success=False,
            audit_time=audit_time,
            error=f"Unexpected error: {e}",
        )

