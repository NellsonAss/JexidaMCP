"""Azure Monitoring tools for metrics, logs, and alerts.

Provides MCP tools for:
- Getting metrics for resources
- Querying Log Analytics workspaces
- Listing active alerts
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from .auth import (
    get_credential_and_subscription,
    get_azure_credential,
    AzureError,
    wrap_azure_error,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Input/Output Schemas
# =============================================================================

class AzureMonitoringGetMetricsInput(BaseModel):
    """Input schema for azure_monitoring_get_metrics."""
    resource_id: str = Field(
        description="Full Azure resource ID to get metrics for"
    )
    metric_names: List[str] = Field(
        description="List of metric names to retrieve (e.g., ['Percentage CPU', 'Network In'])"
    )
    timespan: str = Field(
        default="PT1H",
        description="ISO 8601 duration (e.g., 'PT1H' for 1 hour, 'P1D' for 1 day)"
    )
    interval: Optional[str] = Field(
        default="PT5M",
        description="Metric granularity (e.g., 'PT5M' for 5 minutes, 'PT1H' for 1 hour)"
    )
    aggregation: Optional[List[str]] = Field(
        default=None,
        description="Aggregation types: Average, Total, Count, Maximum, Minimum"
    )


class MetricValue(BaseModel):
    """A single metric data point."""
    timestamp: str = Field(description="ISO 8601 timestamp")
    average: Optional[float] = Field(default=None, description="Average value")
    total: Optional[float] = Field(default=None, description="Total value")
    count: Optional[float] = Field(default=None, description="Count value")
    maximum: Optional[float] = Field(default=None, description="Maximum value")
    minimum: Optional[float] = Field(default=None, description="Minimum value")


class MetricResult(BaseModel):
    """Result for a single metric."""
    name: str = Field(description="Metric name")
    unit: str = Field(default="", description="Metric unit")
    timeseries: List[MetricValue] = Field(default_factory=list, description="Metric values over time")


class AzureMonitoringGetMetricsOutput(BaseModel):
    """Output schema for azure_monitoring_get_metrics."""
    success: bool = Field(description="Whether the request succeeded")
    resource_id: str = Field(default="", description="Resource ID queried")
    metrics: List[MetricResult] = Field(default_factory=list, description="Metric results")
    timespan: str = Field(default="", description="Time span queried")
    interval: str = Field(default="", description="Metric interval")
    error: str = Field(default="", description="Error message if failed")


class AzureMonitoringQueryLogsInput(BaseModel):
    """Input schema for azure_monitoring_query_logs."""
    workspace_id: str = Field(
        description="Log Analytics workspace ID (GUID)"
    )
    kusto_query: str = Field(
        description="Kusto Query Language (KQL) query"
    )
    timespan: str = Field(
        default="P1D",
        description="ISO 8601 duration for query timespan"
    )


class LogQueryResult(BaseModel):
    """Result from a log query."""
    columns: List[str] = Field(default_factory=list, description="Column names")
    rows: List[List[Any]] = Field(default_factory=list, description="Data rows")
    row_count: int = Field(default=0, description="Number of rows returned")


class AzureMonitoringQueryLogsOutput(BaseModel):
    """Output schema for azure_monitoring_query_logs."""
    success: bool = Field(description="Whether the query succeeded")
    workspace_id: str = Field(default="", description="Workspace ID queried")
    result: Optional[LogQueryResult] = Field(default=None, description="Query result")
    query: str = Field(default="", description="Query executed")
    error: str = Field(default="", description="Error message if failed")


class AzureMonitoringListAlertsInput(BaseModel):
    """Input schema for azure_monitoring_list_alerts."""
    subscription_id: Optional[str] = Field(
        default=None,
        description="Subscription ID (uses default if not provided)"
    )
    filter: Optional[str] = Field(
        default=None,
        description="OData filter expression (e.g., \"severity eq 'Sev1'\")"
    )
    state_filter: Optional[str] = Field(
        default=None,
        description="Filter by alert state: New, Acknowledged, Closed"
    )


class AlertInfo(BaseModel):
    """Information about an alert."""
    id: str = Field(description="Alert ID")
    name: str = Field(description="Alert name")
    severity: str = Field(default="", description="Alert severity (Sev0-Sev4)")
    state: str = Field(default="", description="Alert state")
    target_resource: str = Field(default="", description="Target resource ID")
    target_resource_name: str = Field(default="", description="Target resource name")
    target_resource_type: str = Field(default="", description="Target resource type")
    fired_time: str = Field(default="", description="When the alert was triggered")
    description: str = Field(default="", description="Alert description")


class AzureMonitoringListAlertsOutput(BaseModel):
    """Output schema for azure_monitoring_list_alerts."""
    success: bool = Field(description="Whether the request succeeded")
    alerts: List[AlertInfo] = Field(default_factory=list, description="List of alerts")
    count: int = Field(default=0, description="Number of alerts")
    subscription_id: str = Field(default="", description="Subscription ID searched")
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# Tool Implementations
# =============================================================================

async def azure_monitoring_get_metrics(
    params: AzureMonitoringGetMetricsInput
) -> AzureMonitoringGetMetricsOutput:
    """Get metrics for an Azure resource.
    
    Args:
        params.resource_id: Full Azure resource ID
        params.metric_names: List of metric names
        params.timespan: ISO 8601 duration
        params.interval: Metric granularity
        params.aggregation: Aggregation types
        
    Returns:
        Metric data with timestamps and values
    """
    logger.info(f"Getting metrics for: {params.resource_id}")
    
    try:
        from azure.mgmt.monitor import MonitorManagementClient
        from azure.mgmt.monitor.models import MetricAggregationType
        
        # Parse resource ID to get subscription
        parts = params.resource_id.strip("/").split("/")
        subscription_id = None
        for i, part in enumerate(parts):
            if part.lower() == "subscriptions" and i + 1 < len(parts):
                subscription_id = parts[i + 1]
                break
        
        if not subscription_id:
            return AzureMonitoringGetMetricsOutput(
                success=False,
                error="Could not parse subscription ID from resource ID",
            )
        
        credential = get_azure_credential()
        client = MonitorManagementClient(credential, subscription_id)
        
        # Build aggregation list
        aggregations = params.aggregation or ["Average"]
        
        # Query metrics
        response = client.metrics.list(
            resource_uri=params.resource_id,
            metricnames=",".join(params.metric_names),
            timespan=params.timespan,
            interval=params.interval,
            aggregation=",".join(aggregations),
        )
        
        # Parse response
        metrics = []
        for metric in response.value:
            timeseries_data = []
            
            if metric.timeseries:
                for ts in metric.timeseries:
                    if ts.data:
                        for data_point in ts.data:
                            timeseries_data.append(MetricValue(
                                timestamp=data_point.time_stamp.isoformat() if data_point.time_stamp else "",
                                average=data_point.average,
                                total=data_point.total,
                                count=data_point.count,
                                maximum=data_point.maximum,
                                minimum=data_point.minimum,
                            ))
            
            metrics.append(MetricResult(
                name=metric.name.value if metric.name else "",
                unit=metric.unit.value if metric.unit else "",
                timeseries=timeseries_data,
            ))
        
        logger.info(f"Retrieved {len(metrics)} metrics")
        
        return AzureMonitoringGetMetricsOutput(
            success=True,
            resource_id=params.resource_id,
            metrics=metrics,
            timespan=params.timespan,
            interval=params.interval or "",
        )
        
    except AzureError as e:
        logger.error(f"Azure error getting metrics: {e}")
        return AzureMonitoringGetMetricsOutput(
            success=False,
            resource_id=params.resource_id,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        wrapped = wrap_azure_error(e)
        return AzureMonitoringGetMetricsOutput(
            success=False,
            resource_id=params.resource_id,
            error=wrapped.message,
        )


async def azure_monitoring_query_logs(
    params: AzureMonitoringQueryLogsInput
) -> AzureMonitoringQueryLogsOutput:
    """Query logs from a Log Analytics workspace.
    
    Uses Kusto Query Language (KQL) to query logs.
    
    Example queries:
    - "AzureActivity | where Level == 'Error' | take 10"
    - "Heartbeat | summarize count() by Computer"
    - "AppExceptions | where timestamp > ago(1d)"
    
    Args:
        params.workspace_id: Log Analytics workspace ID
        params.kusto_query: KQL query
        params.timespan: Query timespan
        
    Returns:
        Query results with columns and rows
    """
    logger.info(f"Querying logs in workspace: {params.workspace_id}")
    
    try:
        from azure.monitor.query import LogsQueryClient, LogsQueryStatus
        
        credential = get_azure_credential()
        client = LogsQueryClient(credential)
        
        # Parse timespan into timedelta
        # Simple parsing for common formats
        timespan_td = timedelta(days=1)  # Default
        ts = params.timespan.upper()
        if ts.startswith("PT"):
            # Duration format like PT1H, PT30M
            if "H" in ts:
                hours = int(ts.replace("PT", "").replace("H", "").split("M")[0])
                timespan_td = timedelta(hours=hours)
            elif "M" in ts:
                minutes = int(ts.replace("PT", "").replace("M", ""))
                timespan_td = timedelta(minutes=minutes)
        elif ts.startswith("P"):
            # Period format like P1D, P7D
            if "D" in ts:
                days = int(ts.replace("P", "").replace("D", ""))
                timespan_td = timedelta(days=days)
        
        # Execute query
        response = client.query_workspace(
            workspace_id=params.workspace_id,
            query=params.kusto_query,
            timespan=timespan_td,
        )
        
        # Check status
        if response.status == LogsQueryStatus.PARTIAL:
            logger.warning("Query returned partial results")
        elif response.status == LogsQueryStatus.FAILURE:
            return AzureMonitoringQueryLogsOutput(
                success=False,
                workspace_id=params.workspace_id,
                query=params.kusto_query,
                error="Query failed with no results",
            )
        
        # Parse results
        columns = []
        rows = []
        
        if response.tables:
            table = response.tables[0]
            columns = [col.name for col in table.columns]
            rows = [list(row) for row in table.rows]
        
        result = LogQueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
        )
        
        logger.info(f"Query returned {len(rows)} rows")
        
        return AzureMonitoringQueryLogsOutput(
            success=True,
            workspace_id=params.workspace_id,
            result=result,
            query=params.kusto_query,
        )
        
    except ImportError:
        logger.error("azure-monitor-query package not installed")
        return AzureMonitoringQueryLogsOutput(
            success=False,
            workspace_id=params.workspace_id,
            query=params.kusto_query,
            error="Log query SDK not installed. Install with: pip install azure-monitor-query",
        )
    except AzureError as e:
        logger.error(f"Azure error querying logs: {e}")
        return AzureMonitoringQueryLogsOutput(
            success=False,
            workspace_id=params.workspace_id,
            query=params.kusto_query,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to query logs: {e}")
        wrapped = wrap_azure_error(e)
        return AzureMonitoringQueryLogsOutput(
            success=False,
            workspace_id=params.workspace_id,
            query=params.kusto_query,
            error=wrapped.message,
        )


async def azure_monitoring_list_alerts(
    params: AzureMonitoringListAlertsInput
) -> AzureMonitoringListAlertsOutput:
    """List active alerts in a subscription.
    
    Args:
        params.subscription_id: Subscription ID
        params.filter: OData filter expression
        params.state_filter: Filter by alert state
        
    Returns:
        List of alerts with details
    """
    logger.info("Listing alerts")
    
    try:
        from azure.mgmt.alertsmanagement import AlertsManagementClient
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = AlertsManagementClient(credential, subscription_id)
        
        # Build filter
        filter_str = params.filter
        if params.state_filter and not filter_str:
            filter_str = f"alertState eq '{params.state_filter}'"
        elif params.state_filter:
            filter_str = f"{filter_str} and alertState eq '{params.state_filter}'"
        
        # List alerts
        alerts = []
        
        if filter_str:
            alert_list = client.alerts.get_all(filter=filter_str)
        else:
            alert_list = client.alerts.get_all()
        
        for alert in alert_list:
            props = alert.properties if hasattr(alert, 'properties') else None
            essentials = props.essentials if props and hasattr(props, 'essentials') else None
            
            if essentials:
                alerts.append(AlertInfo(
                    id=alert.id or "",
                    name=alert.name or "",
                    severity=essentials.severity or "",
                    state=essentials.alert_state or "",
                    target_resource=essentials.target_resource or "",
                    target_resource_name=essentials.target_resource_name or "",
                    target_resource_type=essentials.target_resource_type or "",
                    fired_time=essentials.start_date_time.isoformat() if essentials.start_date_time else "",
                    description=essentials.description or "",
                ))
            else:
                # Fallback for different alert structure
                alerts.append(AlertInfo(
                    id=alert.id or "",
                    name=alert.name or "",
                ))
        
        logger.info(f"Found {len(alerts)} alerts")
        
        return AzureMonitoringListAlertsOutput(
            success=True,
            alerts=alerts,
            count=len(alerts),
            subscription_id=subscription_id,
        )
        
    except ImportError:
        logger.error("azure-mgmt-alertsmanagement package not installed")
        return AzureMonitoringListAlertsOutput(
            success=False,
            error="Alerts Management SDK not installed. Install with: pip install azure-mgmt-alertsmanagement",
        )
    except AzureError as e:
        logger.error(f"Azure error listing alerts: {e}")
        return AzureMonitoringListAlertsOutput(
            success=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to list alerts: {e}")
        wrapped = wrap_azure_error(e)
        return AzureMonitoringListAlertsOutput(
            success=False,
            error=wrapped.message,
        )

