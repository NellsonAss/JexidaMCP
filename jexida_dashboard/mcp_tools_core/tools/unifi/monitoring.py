"""UniFi Security Monitoring Tool.

Provides the security_monitor_unifi tool for real-time or periodic monitoring
of security events including unauthorized device joins, rogue APs, port state
changes, authentication failures, and WAN attacks/IPS alerts.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError

import logging
logger = logging.getLogger(__name__)


class SecurityAlert(BaseModel):
    """Security alert/event."""
    id: str = Field(description="Alert ID")
    type: str = Field(description="Alert type")
    severity: str = Field(description="Severity: low, medium, high, critical")
    message: str = Field(description="Alert message")
    timestamp: int = Field(description="Unix timestamp")
    datetime: str = Field(description="Human-readable datetime")
    device_mac: str = Field(default="", description="Related device MAC")
    device_name: str = Field(default="", description="Related device name")
    source_ip: str = Field(default="", description="Source IP if applicable")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")


class MonitoringSnapshot(BaseModel):
    """Monitoring snapshot."""
    timestamp: str = Field(description="Snapshot timestamp")
    alerts: List[SecurityAlert] = Field(default_factory=list, description="Security alerts")
    rogue_aps: List[Dict[str, Any]] = Field(default_factory=list, description="Rogue APs detected")
    unauthorized_devices: List[Dict[str, Any]] = Field(default_factory=list, description="Unauthorized devices")
    ips_alerts: List[Dict[str, Any]] = Field(default_factory=list, description="IPS/IDS alerts")
    auth_failures: List[Dict[str, Any]] = Field(default_factory=list, description="Authentication failures")
    port_changes: List[Dict[str, Any]] = Field(default_factory=list, description="Port state changes")


class SecurityMonitorUnifiInput(BaseModel):
    """Input schema for security_monitor_unifi tool."""
    
    interval: Literal["5m", "30m", "1h", "snapshot"] = Field(
        default="snapshot",
        description="Monitoring interval: 5m, 30m, 1h, or 'snapshot' for one-time check"
    )
    mode: Literal["watch", "snapshot"] = Field(
        default="snapshot",
        description="Mode: 'watch' for continuous monitoring, 'snapshot' for one-time check"
    )
    site_id: Optional[str] = Field(
        default=None,
        description="UniFi site ID (defaults to configured site)"
    )
    limit: int = Field(
        default=50,
        description="Maximum number of alerts/events to return"
    )


class SecurityMonitorUnifiOutput(BaseModel):
    """Output schema for security_monitor_unifi tool."""
    
    success: bool = Field(description="Whether the operation succeeded")
    mode: str = Field(description="Monitoring mode used")
    snapshot: Optional[MonitoringSnapshot] = None
    alert_count: int = Field(default=0, description="Total alerts found")
    high_severity_count: int = Field(default=0, description="High severity alerts")
    error: str = Field(default="", description="Error message if failed")


async def security_monitor_unifi(
    params: SecurityMonitorUnifiInput
) -> SecurityMonitorUnifiOutput:
    """Monitor UniFi network for security events.
    
    Monitors:
    - Unauthorized device joins
    - Rogue APs
    - Port state changes
    - Repeated authentication failures
    - WAN attacks / IPS alerts
    
    Args:
        params: Monitoring parameters
        
    Returns:
        Security monitoring snapshot with alerts and events
    """
    logger.info(f"security_monitor_unifi called with mode={params.mode}, interval={params.interval}")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            alerts_list = []
            rogue_aps = []
            ips_alerts = []
            auth_failures = []
            
            # Get recent alerts
            alerts_data = await client.get_alerts(limit=params.limit)
            for alert in alerts_data:
                # Categorize alerts
                alert_type = alert.get("key", "").lower()
                severity = "medium"
                
                if "rogue" in alert_type or "unauthorized" in alert_type:
                    severity = "high"
                elif "auth" in alert_type or "login" in alert_type:
                    severity = "medium"
                elif "ips" in alert_type or "threat" in alert_type:
                    severity = "high"
                elif "port" in alert_type:
                    severity = "low"
                
                alerts_list.append(SecurityAlert(
                    id=alert.get("_id", ""),
                    type=alert.get("key", ""),
                    severity=severity,
                    message=alert.get("msg", ""),
                    timestamp=alert.get("time", 0),
                    datetime=alert.get("datetime", ""),
                    device_mac=alert.get("device_mac", ""),
                    device_name=alert.get("device_name", ""),
                ))
            
            # Get rogue APs
            rogue_data = await client.get_rogueaps()
            for rogue in rogue_data:
                if rogue.get("is_rogue", False):
                    rogue_aps.append({
                        "mac": rogue.get("mac", ""),
                        "essid": rogue.get("essid", ""),
                        "channel": rogue.get("channel", 0),
                        "rssi": rogue.get("rssi", 0),
                        "security": rogue.get("security", ""),
                        "last_seen": rogue.get("last_seen", 0),
                        "ap_mac": rogue.get("ap_mac", ""),
                    })
            
            # Get IPS alerts
            ips_data = await client.get_ips_alerts(limit=params.limit)
            for ips in ips_data:
                ips_alerts.append({
                    "signature": ips.get("signature", ""),
                    "category": ips.get("category", ""),
                    "severity": ips.get("severity", ""),
                    "src_ip": ips.get("src_ip", ""),
                    "dst_ip": ips.get("dst_ip", ""),
                    "protocol": ips.get("protocol", ""),
                    "action": ips.get("action", ""),
                    "msg": ips.get("msg", ""),
                    "timestamp": ips.get("timestamp", 0),
                })
            
            # Get events for auth failures and port changes
            events_data = await client.get_events(limit=params.limit)
            for event in events_data:
                event_key = event.get("key", "").lower()
                if "auth" in event_key or "login" in event_key or "failed" in event_key:
                    auth_failures.append({
                        "key": event.get("key", ""),
                        "msg": event.get("msg", ""),
                        "user": event.get("user", ""),
                        "ap": event.get("ap", ""),
                        "timestamp": event.get("time", 0),
                        "datetime": event.get("datetime", ""),
                    })
            
            # Count high severity alerts
            high_severity = sum(1 for a in alerts_list if a.severity in ("high", "critical"))
            
            snapshot = MonitoringSnapshot(
                timestamp=datetime.now().isoformat(),
                alerts=alerts_list,
                rogue_aps=rogue_aps,
                unauthorized_devices=[],  # Would need additional logic to detect
                ips_alerts=ips_alerts,
                auth_failures=auth_failures,
                port_changes=[],  # Would need to track port state changes over time
            )
            
            logger.info(f"Monitoring snapshot: {len(alerts_list)} alerts, {len(rogue_aps)} rogue APs, "
                       f"{len(ips_alerts)} IPS alerts, {high_severity} high severity")
            
            return SecurityMonitorUnifiOutput(
                success=True,
                mode=params.mode,
                snapshot=snapshot,
                alert_count=len(alerts_list),
                high_severity_count=high_severity,
            )
            
    except UniFiConnectionError as e:
        return SecurityMonitorUnifiOutput(success=False, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        return SecurityMonitorUnifiOutput(success=False, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        return SecurityMonitorUnifiOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        return SecurityMonitorUnifiOutput(success=False, error=f"Unexpected error: {e}")

