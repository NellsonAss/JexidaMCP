"""Network hardening audit tool.

Provides the network_hardening_audit tool that evaluates UniFi configuration
against a security policy and generates findings and recommendations.
"""

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from logging_config import get_logger, ToolInvocationLogger
from tool_registry import tool

from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError
from .network_scan import network_scan_local, NetworkScanInput

logger = get_logger(__name__)


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
    severity: Severity
    category: str
    title: str
    description: str
    current_value: Any = None
    recommended_value: Any = None
    remediation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "current_value": self.current_value,
            "recommended_value": self.recommended_value,
            "remediation": self.remediation,
        }


@dataclass
class RecommendedChange:
    """A recommended configuration change."""
    category: str  # wifi, firewall, vlan, upnp
    change_type: str  # The specific edit type
    target: str  # Name/ID of target
    changes: Dict[str, Any]  # The actual changes
    finding_ids: List[str]  # Related findings
    phase: int = 1  # Phase for phased rollout (1=low-risk, 2=firewall, 3=vlan)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "change_type": self.change_type,
            "target": self.target,
            "changes": self.changes,
            "finding_ids": self.finding_ids,
            "phase": self.phase,
        }


def load_policy(policy_path: Optional[str] = None) -> Dict[str, Any]:
    """Load security policy from JSON file.
    
    Args:
        policy_path: Path to policy file (defaults to security_policy.json)
        
    Returns:
        Parsed policy dictionary
    """
    if policy_path is None:
        # Default to security_policy.json in mcp_server_files
        base_dir = Path(__file__).parent.parent.parent
        policy_path = base_dir / "security_policy.json"
    else:
        policy_path = Path(policy_path)
    
    if not policy_path.exists():
        logger.warning(f"Policy file not found: {policy_path}, using defaults")
        return {}
    
    with open(policy_path, "r") as f:
        return json.load(f)


class PolicyEvaluator:
    """Evaluates configuration against security policy."""
    
    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy
        self.findings: List[Finding] = []
        self.recommendations: List[RecommendedChange] = []
        self._finding_counter = 0
    
    def _next_finding_id(self) -> str:
        self._finding_counter += 1
        return f"F{self._finding_counter:03d}"
    
    def evaluate_wifi(self, wifi_networks: List[Dict[str, Any]]) -> None:
        """Evaluate WiFi configuration against policy."""
        wifi_policy = self.policy.get("wifi", {})
        
        for network in wifi_networks:
            ssid = network.get("name", network.get("ssid", "Unknown"))
            enabled = network.get("enabled", False)
            
            if not enabled:
                continue
            
            security = network.get("security", "open")
            wpa_mode = network.get("wpa_mode", "")
            is_guest = network.get("is_guest", False)
            client_isolation = network.get("client_isolation", network.get("l2_isolation", False))
            wpa3_support = network.get("wpa3_support", False)
            wpa3_transition = network.get("wpa3_transition", False)
            pmf_mode = network.get("pmf_mode", "disabled")
            
            # Check for open networks
            if security == "open":
                require_encryption = wifi_policy.get("require_encryption", {})
                allowed = wifi_policy.get("disallow_open_except", {}).get("allowed_ssids", [])
                
                if require_encryption.get("enabled", True) and ssid not in allowed:
                    finding_id = self._next_finding_id()
                    self.findings.append(Finding(
                        id=finding_id,
                        severity=Severity(require_encryption.get("severity", "high")),
                        category="wifi",
                        title=f"Open WiFi network: {ssid}",
                        description="WiFi network has no encryption enabled",
                        current_value="open",
                        recommended_value="WPA2 or WPA3",
                        remediation=f"Enable WPA2 or WPA3 encryption on SSID '{ssid}'",
                    ))
                    
                    self.recommendations.append(RecommendedChange(
                        category="wifi",
                        change_type="update",
                        target=ssid,
                        changes={
                            "ssid": ssid,
                            "security": "wpapsk",
                            "wpa_mode": "wpa2",
                        },
                        finding_ids=[finding_id],
                        phase=1,
                    ))
            
            # Check WPA version
            elif wpa_mode and "wpa1" in wpa_mode.lower():
                min_wpa = wifi_policy.get("min_wpa_version", {})
                if min_wpa.get("value", "WPA2") in ["WPA2", "WPA3"]:
                    finding_id = self._next_finding_id()
                    self.findings.append(Finding(
                        id=finding_id,
                        severity=Severity(min_wpa.get("severity", "high")),
                        category="wifi",
                        title=f"Weak encryption on {ssid}",
                        description="WiFi network using deprecated WPA1 encryption",
                        current_value=wpa_mode,
                        recommended_value="WPA2 or WPA3",
                        remediation=f"Upgrade '{ssid}' to WPA2 or WPA3",
                    ))
                    
                    self.recommendations.append(RecommendedChange(
                        category="wifi",
                        change_type="update",
                        target=ssid,
                        changes={
                            "ssid": ssid,
                            "wpa_mode": "wpa2",
                        },
                        finding_ids=[finding_id],
                        phase=1,
                    ))
            
            # Recommend WPA3
            recommend_wpa3 = wifi_policy.get("recommend_wpa3", {})
            if recommend_wpa3.get("enabled", True):
                if not wpa3_support and not wpa3_transition and security != "open":
                    finding_id = self._next_finding_id()
                    self.findings.append(Finding(
                        id=finding_id,
                        severity=Severity(recommend_wpa3.get("severity", "low")),
                        category="wifi",
                        title=f"WPA3 not enabled on {ssid}",
                        description="Consider enabling WPA3 or WPA3 transition mode for improved security",
                        current_value="WPA2 only",
                        recommended_value="WPA3 transition mode",
                        remediation=f"Enable WPA3 transition mode on '{ssid}'",
                    ))
            
            # Check guest network isolation
            if is_guest:
                guest_isolation = wifi_policy.get("require_client_isolation_for_guest", {})
                if guest_isolation.get("enabled", True) and not client_isolation:
                    finding_id = self._next_finding_id()
                    self.findings.append(Finding(
                        id=finding_id,
                        severity=Severity(guest_isolation.get("severity", "medium")),
                        category="wifi",
                        title=f"Guest network lacks client isolation: {ssid}",
                        description="Guest network should isolate clients from each other",
                        current_value=False,
                        recommended_value=True,
                        remediation=f"Enable client isolation (L2 isolation) on '{ssid}'",
                    ))
                    
                    self.recommendations.append(RecommendedChange(
                        category="wifi",
                        change_type="update",
                        target=ssid,
                        changes={
                            "ssid": ssid,
                            "l2_isolation": True,
                        },
                        finding_ids=[finding_id],
                        phase=1,
                    ))
    
    def evaluate_remote_access(self, remote_settings: Dict[str, Any]) -> None:
        """Evaluate remote access settings against policy."""
        remote_policy = self.policy.get("remote_access", {})
        
        # Check UPnP
        upnp_policy = remote_policy.get("upnp_allowed", {})
        if not upnp_policy.get("enabled", False):
            if remote_settings.get("upnp_enabled", False):
                finding_id = self._next_finding_id()
                self.findings.append(Finding(
                    id=finding_id,
                    severity=Severity(upnp_policy.get("severity", "high")),
                    category="remote_access",
                    title="UPnP is enabled",
                    description="UPnP allows devices to automatically open ports, which is a security risk",
                    current_value=True,
                    recommended_value=False,
                    remediation="Disable UPnP on the gateway",
                ))
                
                self.recommendations.append(RecommendedChange(
                    category="upnp",
                    change_type="update",
                    target="upnp_settings",
                    changes={
                        "upnp_enabled": False,
                    },
                    finding_ids=[finding_id],
                    phase=1,
                ))
        
        # Check NAT-PMP
        nat_pmp_policy = remote_policy.get("nat_pmp_allowed", {})
        if not nat_pmp_policy.get("enabled", False):
            if remote_settings.get("upnp_nat_pmp_enabled", False):
                finding_id = self._next_finding_id()
                self.findings.append(Finding(
                    id=finding_id,
                    severity=Severity(nat_pmp_policy.get("severity", "high")),
                    category="remote_access",
                    title="NAT-PMP is enabled",
                    description="NAT-PMP allows automatic port mapping, similar security risk to UPnP",
                    current_value=True,
                    recommended_value=False,
                    remediation="Disable NAT-PMP on the gateway",
                ))
                
                self.recommendations.append(RecommendedChange(
                    category="upnp",
                    change_type="update",
                    target="upnp_settings",
                    changes={
                        "upnp_nat_pmp_enabled": False,
                    },
                    finding_ids=[finding_id],
                    phase=1,
                ))
        
        # Check SSH password auth
        ssh_policy = remote_policy.get("ssh_password_auth_allowed", {})
        if not ssh_policy.get("enabled", False):
            if remote_settings.get("ssh_password_auth", False):
                finding_id = self._next_finding_id()
                self.findings.append(Finding(
                    id=finding_id,
                    severity=Severity(ssh_policy.get("severity", "medium")),
                    category="remote_access",
                    title="SSH password authentication enabled",
                    description="SSH password authentication is less secure than key-based auth",
                    current_value=True,
                    recommended_value=False,
                    remediation="Disable SSH password authentication, use SSH keys instead",
                ))
    
    def evaluate_threat_management(self, threat_settings: Dict[str, Any]) -> None:
        """Evaluate threat management settings against policy."""
        threat_policy = self.policy.get("threat_management", {})
        
        ids_policy = threat_policy.get("require_ids_ips", {})
        if ids_policy.get("enabled", True):
            if not threat_settings.get("ids_ips_enabled", False):
                finding_id = self._next_finding_id()
                recommended_mode = ids_policy.get("recommended_mode", "ips")
                self.findings.append(Finding(
                    id=finding_id,
                    severity=Severity(ids_policy.get("severity", "medium")),
                    category="threat_management",
                    title="IDS/IPS is disabled",
                    description="Intrusion Detection/Prevention System provides network threat protection",
                    current_value="disabled",
                    recommended_value=recommended_mode,
                    remediation=f"Enable IDS/IPS in {recommended_mode} mode",
                ))
            elif threat_settings.get("mode", "disabled") == "ids":
                current_mode = threat_settings.get("mode", "disabled")
                recommended = ids_policy.get("recommended_mode", "ips")
                if recommended == "ips" and current_mode == "ids":
                    finding_id = self._next_finding_id()
                    self.findings.append(Finding(
                        id=finding_id,
                        severity=Severity.LOW,
                        category="threat_management",
                        title="IDS mode only (IPS recommended)",
                        description="IPS mode actively blocks threats while IDS only detects",
                        current_value="ids",
                        recommended_value="ips",
                        remediation="Consider switching from IDS to IPS mode",
                    ))
    
    def evaluate_vlans(self, networks: List[Dict[str, Any]], wifi_networks: List[Dict[str, Any]]) -> None:
        """Evaluate VLAN configuration against policy."""
        vlan_policy = self.policy.get("vlans", {})
        
        # Check for guest VLAN
        guest_vlan_policy = vlan_policy.get("require_guest_vlan", {})
        if guest_vlan_policy.get("enabled", True):
            guest_wifis = [w for w in wifi_networks if w.get("is_guest", False) and w.get("enabled", False)]
            
            for guest_wifi in guest_wifis:
                ssid = guest_wifi.get("name", "Unknown")
                if not guest_wifi.get("vlan_enabled", False):
                    finding_id = self._next_finding_id()
                    self.findings.append(Finding(
                        id=finding_id,
                        severity=Severity(guest_vlan_policy.get("severity", "medium")),
                        category="vlan",
                        title=f"Guest network not on separate VLAN: {ssid}",
                        description="Guest networks should be isolated on their own VLAN",
                        current_value="No VLAN",
                        recommended_value="VLAN enabled",
                        remediation=f"Create a guest VLAN and assign '{ssid}' to it",
                    ))
    
    def evaluate_firewall(self, firewall_rules: Dict[str, List[Dict[str, Any]]]) -> None:
        """Evaluate firewall rules against policy."""
        fw_policy = self.policy.get("firewall", {})
        
        # Check for overly permissive rules
        flag_allow_all = fw_policy.get("flag_allow_all_rules", {})
        if flag_allow_all.get("enabled", True):
            for ruleset_name, rules in firewall_rules.items():
                for rule in rules:
                    if not rule.get("enabled", True):
                        continue
                    
                    action = rule.get("action", "")
                    protocol = rule.get("protocol", "all")
                    dst_port = rule.get("dst_port", "")
                    source = rule.get("source", "any")
                    destination = rule.get("destination", "any")
                    
                    # Flag rules that allow all protocols with no port restriction
                    if action == "accept" and protocol == "all" and not dst_port:
                        if "any" in source.lower() or "any" in destination.lower():
                            finding_id = self._next_finding_id()
                            rule_name = rule.get("name", "Unnamed rule")
                            self.findings.append(Finding(
                                id=finding_id,
                                severity=Severity(flag_allow_all.get("severity", "high")),
                                category="firewall",
                                title=f"Overly permissive firewall rule: {rule_name}",
                                description=f"Rule in {ruleset_name} allows all traffic",
                                current_value=f"Accept all from {source} to {destination}",
                                recommended_value="Restrict by port/protocol or remove",
                                remediation=f"Review and restrict firewall rule '{rule_name}' in {ruleset_name}",
                            ))
    
    def get_results(self) -> tuple[List[Finding], List[RecommendedChange]]:
        """Get evaluation results."""
        return self.findings, self.recommendations


# -------------------------------------------------------------------------
# Input/Output Models
# -------------------------------------------------------------------------

class NetworkHardeningAuditInput(BaseModel):
    """Input schema for network_hardening_audit tool."""
    
    site_id: Optional[str] = Field(
        default=None,
        description="UniFi site ID (defaults to configured site)"
    )
    run_scan: bool = Field(
        default=False,
        description="Also run a network scan to discover devices"
    )
    scan_subnets: List[str] = Field(
        default_factory=list,
        description="Subnets to scan if run_scan is True (e.g., ['192.168.1.0/24'])"
    )
    policy_path: Optional[str] = Field(
        default=None,
        description="Path to custom security policy JSON file"
    )


class FindingInfo(BaseModel):
    """A security finding."""
    id: str
    severity: str
    category: str
    title: str
    description: str
    current_value: Any = None
    recommended_value: Any = None
    remediation: str = ""


class RecommendedChangeInfo(BaseModel):
    """A recommended change."""
    category: str
    change_type: str
    target: str
    changes: Dict[str, Any]
    finding_ids: List[str]
    phase: int


class NetworkHardeningAuditOutput(BaseModel):
    """Output schema for network_hardening_audit tool."""
    
    success: bool = Field(description="Whether the audit completed successfully")
    findings: List[FindingInfo] = Field(
        default_factory=list,
        description="Security findings with severity levels"
    )
    findings_by_severity: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of findings by severity"
    )
    recommended_changes: List[RecommendedChangeInfo] = Field(
        default_factory=list,
        description="Recommended configuration changes"
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Additional observations and notes"
    )
    scan_results: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Network scan results if run_scan was True"
    )
    error: str = Field(default="", description="Error message if failed")


@tool(
    name="network_hardening_audit",
    description="Perform a comprehensive security audit of UniFi network configuration against best practices",
    input_schema=NetworkHardeningAuditInput,
    output_schema=NetworkHardeningAuditOutput,
    tags=["unifi", "network", "security", "audit"]
)
async def network_hardening_audit(
    params: NetworkHardeningAuditInput
) -> NetworkHardeningAuditOutput:
    """Perform a security audit of the UniFi network.
    
    Evaluates configuration against security policy and generates
    findings with recommended remediations.
    
    Args:
        params: Audit parameters
        
    Returns:
        Audit results with findings and recommendations
    """
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start(
        "network_hardening_audit",
        site_id=params.site_id,
        run_scan=params.run_scan,
    )
    
    notes = []
    scan_results = None
    
    try:
        # Load policy
        policy = load_policy(params.policy_path)
        if not policy:
            notes.append("Using default security policy (policy file not found)")
            policy = {
                "wifi": {"require_encryption": {"enabled": True, "severity": "high"}},
                "remote_access": {"upnp_allowed": {"enabled": False, "severity": "high"}},
                "threat_management": {"require_ids_ips": {"enabled": True, "severity": "medium"}},
            }
        
        evaluator = PolicyEvaluator(policy)
        
        async with UniFiClient(site=params.site_id) as client:
            # Get all relevant settings
            wifi_networks = await client.get_wlans()
            networks = await client.get_networks()
            firewall_rules = await client.get_firewall_rules()
            upnp_settings = await client.get_upnp_settings()
            mgmt_settings = await client.get_mgmt_settings()
            threat_settings = await client.get_threat_management_settings()
            dpi_settings = await client.get_dpi_settings()
            
            # Combine remote access settings
            remote_settings = {
                **upnp_settings,
                "ssh_enabled": mgmt_settings.get("remote_access_enabled", False),
                "ssh_password_auth": mgmt_settings.get("ssh_auth_password_enabled", False),
                "cloud_access_enabled": mgmt_settings.get("unifi_remote_access_enabled", False),
            }
            
            # Combine threat settings
            combined_threat = {
                **threat_settings,
                **dpi_settings,
            }
            
            # Run evaluations
            evaluator.evaluate_wifi(wifi_networks)
            evaluator.evaluate_remote_access(remote_settings)
            evaluator.evaluate_threat_management(combined_threat)
            evaluator.evaluate_vlans(networks, wifi_networks)
            evaluator.evaluate_firewall(firewall_rules)
        
        # Optionally run network scan
        if params.run_scan and params.scan_subnets:
            try:
                scan_input = NetworkScanInput(
                    subnets=params.scan_subnets,
                    ports="common",
                )
                scan_output = await network_scan_local(scan_input)
                
                if scan_output.success:
                    scan_results = {
                        "hosts_found": scan_output.hosts_up,
                        "hosts": [h.model_dump() for h in scan_output.hosts],
                    }
                    notes.append(f"Network scan found {scan_output.hosts_up} hosts")
                else:
                    notes.append(f"Network scan failed: {scan_output.error}")
            except Exception as e:
                notes.append(f"Network scan error: {e}")
        
        # Get results
        findings, recommendations = evaluator.get_results()
        
        # Count by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for finding in findings:
            sev = finding.severity.value
            if sev in severity_counts:
                severity_counts[sev] += 1
        
        # Convert to output format
        finding_infos = [
            FindingInfo(
                id=f.id,
                severity=f.severity.value,
                category=f.category,
                title=f.title,
                description=f.description,
                current_value=f.current_value,
                recommended_value=f.recommended_value,
                remediation=f.remediation,
            )
            for f in findings
        ]
        
        recommendation_infos = [
            RecommendedChangeInfo(
                category=r.category,
                change_type=r.change_type,
                target=r.target,
                changes=r.changes,
                finding_ids=r.finding_ids,
                phase=r.phase,
            )
            for r in recommendations
        ]
        
        # Add summary note
        total_findings = len(findings)
        if total_findings == 0:
            notes.append("No security issues found - configuration follows best practices")
        else:
            notes.append(f"Found {total_findings} security issue(s): {severity_counts['high']} high, {severity_counts['medium']} medium, {severity_counts['low']} low")
        
        invocation_logger.success(
            findings_count=total_findings,
            recommendations_count=len(recommendations),
        )
        
        return NetworkHardeningAuditOutput(
            success=True,
            findings=finding_infos,
            findings_by_severity=severity_counts,
            recommended_changes=recommendation_infos,
            notes=notes,
            scan_results=scan_results,
        )
        
    except UniFiConnectionError as e:
        invocation_logger.failure(str(e))
        return NetworkHardeningAuditOutput(
            success=False,
            error=f"Connection error: {e}",
        )
    except UniFiAuthError as e:
        invocation_logger.failure(str(e))
        return NetworkHardeningAuditOutput(
            success=False,
            error=f"Authentication error: {e}",
        )
    except UniFiAPIError as e:
        invocation_logger.failure(str(e))
        return NetworkHardeningAuditOutput(
            success=False,
            error=f"API error: {e}",
        )
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return NetworkHardeningAuditOutput(
            success=False,
            error=f"Unexpected error: {e}",
        )

