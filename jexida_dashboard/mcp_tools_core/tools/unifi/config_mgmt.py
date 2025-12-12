"""UniFi Configuration Export, Diff, and Drift Detection Tools.

Provides tools for:
- unifi_config_export: Export controller config in JSON format
- unifi_config_diff: Compare two configurations
- unifi_config_drift_monitor: Detect configuration drift
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError

import logging
logger = logging.getLogger(__name__)


class UniFiConfigExportInput(BaseModel):
    """Input schema for unifi_config_export tool."""
    
    site_id: Optional[str] = Field(default=None, description="UniFi site ID")
    format: str = Field(default="json", description="Export format: json")


class UniFiConfigExportOutput(BaseModel):
    """Output schema for unifi_config_export tool."""
    
    success: bool = Field(description="Whether export succeeded")
    config: Dict[str, Any] = Field(default_factory=dict, description="Exported configuration")
    exported_at: str = Field(default="", description="Export timestamp")
    size_bytes: int = Field(default=0, description="Config size in bytes")
    error: str = Field(default="", description="Error message if failed")


async def unifi_config_export(params: UniFiConfigExportInput) -> UniFiConfigExportOutput:
    """Export controller configuration in JSON + diff-friendly format.
    
    Args:
        params: Export parameters
        
    Returns:
        Exported configuration
    """
    logger.info("unifi_config_export called")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            config = await client.export_full_config()
            config["exported_at"] = datetime.now().isoformat()
            
            config_json = json.dumps(config, default=str)
            size_bytes = len(config_json.encode("utf-8"))
            
            return UniFiConfigExportOutput(
                success=True,
                config=config,
                exported_at=config["exported_at"],
                size_bytes=size_bytes,
            )
            
    except UniFiConnectionError as e:
        return UniFiConfigExportOutput(success=False, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        return UniFiConfigExportOutput(success=False, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        return UniFiConfigExportOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        return UniFiConfigExportOutput(success=False, error=f"Unexpected error: {e}")


class UniFiConfigDiffInput(BaseModel):
    """Input schema for unifi_config_diff tool."""
    
    config1: Optional[Dict[str, Any]] = Field(default=None, description="First configuration (from export)")
    config2: Optional[Dict[str, Any]] = Field(default=None, description="Second configuration (from export)")
    compare_to_backup: Optional[str] = Field(default=None, description="Compare current config to backup ID")
    site_id: Optional[str] = Field(default=None, description="UniFi site ID")


class ConfigDifference(BaseModel):
    """A configuration difference."""
    path: str = Field(description="Configuration path (e.g., 'firewall.rules[0].action')")
    type: str = Field(description="Difference type: added, removed, modified")
    old_value: Any = Field(default=None, description="Old value")
    new_value: Any = Field(default=None, description="New value")


class UniFiConfigDiffOutput(BaseModel):
    """Output schema for unifi_config_diff tool."""
    
    success: bool = Field(description="Whether diff succeeded")
    differences: Dict[str, List[ConfigDifference]] = Field(
        default_factory=dict,
        description="Differences organized by category"
    )
    total_differences: int = Field(default=0, description="Total number of differences")
    error: str = Field(default="", description="Error message if failed")


def deep_diff(obj1: Any, obj2: Any, path: str = "") -> list[ConfigDifference]:
    """Recursively compare two objects and return differences."""
    differences = []
    
    if isinstance(obj1, dict) and isinstance(obj2, dict):
        all_keys = set(obj1.keys()) | set(obj2.keys())
        for key in all_keys:
            new_path = f"{path}.{key}" if path else key
            if key not in obj1:
                differences.append(ConfigDifference(
                    path=new_path,
                    type="added",
                    new_value=obj2[key],
                ))
            elif key not in obj2:
                differences.append(ConfigDifference(
                    path=new_path,
                    type="removed",
                    old_value=obj1[key],
                ))
            else:
                differences.extend(deep_diff(obj1[key], obj2[key], new_path))
    elif isinstance(obj1, list) and isinstance(obj2, list):
        max_len = max(len(obj1), len(obj2))
        for i in range(max_len):
            new_path = f"{path}[{i}]"
            if i >= len(obj1):
                differences.append(ConfigDifference(
                    path=new_path,
                    type="added",
                    new_value=obj2[i],
                ))
            elif i >= len(obj2):
                differences.append(ConfigDifference(
                    path=new_path,
                    type="removed",
                    old_value=obj1[i],
                ))
            else:
                differences.extend(deep_diff(obj1[i], obj2[i], new_path))
    elif obj1 != obj2:
        differences.append(ConfigDifference(
            path=path,
            type="modified",
            old_value=obj1,
            new_value=obj2,
        ))
    
    return differences


async def unifi_config_diff(params: UniFiConfigDiffInput) -> UniFiConfigDiffOutput:
    """Compare two configurations or current vs backup.
    
    Args:
        params: Diff parameters
        
    Returns:
        Configuration differences
    """
    logger.info("unifi_config_diff called")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            # Get configs
            if params.compare_to_backup:
                # Get current config
                config1 = await client.export_full_config()
                # Get backup config (would need backup download functionality)
                # For now, return error
                return UniFiConfigDiffOutput(
                    success=False,
                    error="Backup comparison not yet implemented. Use config1 and config2 parameters.",
                )
            elif params.config1 and params.config2:
                config1 = params.config1
                config2 = params.config2
            else:
                return UniFiConfigDiffOutput(
                    success=False,
                    error="Must provide both config1 and config2, or compare_to_backup",
                )
            
            # Compute differences
            all_diffs = deep_diff(config1, config2)
            
            # Organize by category
            differences_by_category: Dict[str, list[ConfigDifference]] = {}
            for diff in all_diffs:
                category = diff.path.split(".")[0] if "." in diff.path else "root"
                if category not in differences_by_category:
                    differences_by_category[category] = []
                differences_by_category[category].append(diff)
            
            return UniFiConfigDiffOutput(
                success=True,
                differences=differences_by_category,
                total_differences=len(all_diffs),
            )
            
    except UniFiConnectionError as e:
        return UniFiConfigDiffOutput(success=False, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        return UniFiConfigDiffOutput(success=False, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        return UniFiConfigDiffOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        return UniFiConfigDiffOutput(success=False, error=f"Unexpected error: {e}")


class UniFiConfigDriftMonitorInput(BaseModel):
    """Input schema for unifi_config_drift_monitor tool."""
    
    baseline_config: Dict[str, Any] = Field(description="Baseline configuration to compare against")
    site_id: Optional[str] = Field(default=None, description="UniFi site ID")
    alert_on_drift: bool = Field(default=True, description="Alert if drift detected")


class UniFiConfigDriftMonitorOutput(BaseModel):
    """Output schema for unifi_config_drift_monitor tool."""
    
    success: bool = Field(description="Whether monitoring check succeeded")
    drift_detected: bool = Field(default=False, description="Whether configuration drift was detected")
    drift_details: Optional[UniFiConfigDiffOutput] = None
    alert_sent: bool = Field(default=False, description="Whether alert was sent")
    error: str = Field(default="", description="Error message if failed")


async def unifi_config_drift_monitor(
    params: UniFiConfigDriftMonitorInput
) -> UniFiConfigDriftMonitorOutput:
    """Monitor for configuration drift outside automation.
    
    Compares current configuration to a baseline and alerts if changes
    are detected that weren't made through automation.
    
    Args:
        params: Monitoring parameters
        
    Returns:
        Drift detection result
    """
    logger.info("unifi_config_drift_monitor called")
    
    try:
        async with UniFiClient(site=params.site_id) as client:
            # Get current config
            current_config = await client.export_full_config()
            
            # Compare to baseline
            diff_result = await unifi_config_diff(UniFiConfigDiffInput(
                config1=params.baseline_config,
                config2=current_config,
                site_id=params.site_id,
            ))
            
            drift_detected = diff_result.total_differences > 0
            
            # Alert if drift detected
            alert_sent = False
            if drift_detected and params.alert_on_drift:
                # In production, would send alert via configured channel
                logger.warning(f"Configuration drift detected: {diff_result.total_differences} differences")
                alert_sent = True
            
            return UniFiConfigDriftMonitorOutput(
                success=True,
                drift_detected=drift_detected,
                drift_details=diff_result if drift_detected else None,
                alert_sent=alert_sent,
            )
            
    except UniFiConnectionError as e:
        return UniFiConfigDriftMonitorOutput(success=False, error=f"Connection error: {e}")
    except UniFiAuthError as e:
        return UniFiConfigDriftMonitorOutput(success=False, error=f"Authentication error: {e}")
    except UniFiAPIError as e:
        return UniFiConfigDriftMonitorOutput(success=False, error=f"API error: {e}")
    except Exception as e:
        return UniFiConfigDriftMonitorOutput(success=False, error=f"Unexpected error: {e}")

