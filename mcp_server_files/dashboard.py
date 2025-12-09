"""Dashboard helper functions for monitoring data."""

from typing import Any, Dict

from tool_registry import get_registry


async def get_azure_cost_summary(subscription_id: str) -> Dict[str, Any]:
    """Get Azure cost summary for monitoring dashboard.
    
    Args:
        subscription_id: Azure subscription ID
        
    Returns:
        Cost summary data
    """
    registry = get_registry()
    try:
        result = await registry.execute("azure_cost_get_summary", {
            "subscription_id": subscription_id,
            "time_period": "Last30Days"
        })
        return result
    except Exception as e:
        return {"error": str(e), "success": False}


async def get_unifi_devices() -> Dict[str, Any]:
    """Get UniFi devices for monitoring dashboard.
    
    Returns:
        List of UniFi devices
    """
    registry = get_registry()
    try:
        result = await registry.execute("unifi_list_devices", {})
        return result
    except Exception as e:
        return {"error": str(e), "success": False}


async def get_synology_info() -> Dict[str, Any]:
    """Get Synology NAS info for monitoring dashboard.
    
    Returns:
        Synology system info
    """
    registry = get_registry()
    try:
        result = await registry.execute("synology_get_system_info", {})
        return result
    except Exception as e:
        return {"error": str(e), "success": False}


async def get_monitoring_data() -> Dict[str, Any]:
    """Get all monitoring data for dashboard.
    
    Returns:
        Dictionary with monitoring data from various sources
    """
    # This is a placeholder - will be expanded based on available tools
    return {
        "azure_costs": {},
        "unifi_devices": {},
        "synology": {},
        "system_health": {
            "status": "healthy",
            "uptime": "N/A"
        }
    }

