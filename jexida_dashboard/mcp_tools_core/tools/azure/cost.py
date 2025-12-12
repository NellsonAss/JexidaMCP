"""Azure Cost tools for cost management and analysis.

Provides MCP tools for:
- Getting cost summaries
- Getting top cost drivers
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, field_validator

from .auth import (
    get_credential_and_subscription,
    AzureError,
    wrap_azure_error,
)
from .utils import validate_subscription_id

logger = logging.getLogger(__name__)


# =============================================================================
# Input/Output Schemas
# =============================================================================

class TimePeriod(str, Enum):
    """Time period options for cost queries."""
    LAST_7_DAYS = "Last7Days"
    LAST_30_DAYS = "Last30Days"
    MONTH_TO_DATE = "MonthToDate"


class CostBreakdownItem(BaseModel):
    """Individual item in cost breakdown."""
    name: str = Field(description="Resource group or service name")
    cost: float = Field(description="Cost amount")


class AzureCostInput(BaseModel):
    """Input schema for azure_cost_get_summary tool."""
    subscription_id: str = Field(
        description="Azure subscription ID (GUID format)"
    )
    resource_group: Optional[str] = Field(
        default=None,
        description="Optional resource group to filter costs"
    )
    time_period: TimePeriod = Field(
        default=TimePeriod.LAST_30_DAYS,
        description="Time period for cost summary"
    )

    @field_validator("subscription_id")
    @classmethod
    def validate_subscription(cls, v: str) -> str:
        """Validate subscription ID format."""
        if not validate_subscription_id(v):
            raise ValueError(
                "Invalid subscription ID format. Expected GUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            )
        return v


class AzureCostOutput(BaseModel):
    """Output schema for azure_cost_get_summary tool."""
    success: bool = Field(default=True, description="Whether the request succeeded")
    total_cost: float = Field(description="Total cost for the period")
    currency: str = Field(description="Currency code (e.g., USD, EUR)")
    breakdown: List[CostBreakdownItem] = Field(
        description="Cost breakdown by resource group or service"
    )
    time_period: str = Field(description="The time period queried")
    is_mock_data: bool = Field(
        default=False,
        description="Indicates if this is mock/stub data"
    )
    error: str = Field(default="", description="Error message if failed")


class AzureCostGetTopCostDriversInput(BaseModel):
    """Input schema for azure_cost_get_top_cost_drivers."""
    scope: str = Field(
        description="Cost scope: '/subscriptions/{id}' or '/subscriptions/{id}/resourceGroups/{name}'"
    )
    time_period: Dict[str, str] = Field(
        description="Time period with 'from' and 'to' dates (YYYY-MM-DD format)"
    )
    top_n: int = Field(
        default=10,
        description="Number of top cost drivers to return"
    )
    group_by: str = Field(
        default="ResourceGroup",
        description="Grouping: ResourceGroup, ServiceName, ResourceType, ResourceId"
    )


class CostDriver(BaseModel):
    """A top cost driver."""
    name: str = Field(description="Resource/service/group name")
    cost: float = Field(description="Cost amount")
    currency: str = Field(description="Currency code")
    percentage: float = Field(default=0.0, description="Percentage of total")


class AzureCostGetTopCostDriversOutput(BaseModel):
    """Output schema for azure_cost_get_top_cost_drivers."""
    success: bool = Field(description="Whether the request succeeded")
    cost_drivers: List[CostDriver] = Field(default_factory=list, description="Top cost drivers")
    total_cost: float = Field(default=0.0, description="Total cost for the period")
    currency: str = Field(default="USD", description="Currency code")
    scope: str = Field(default="", description="Scope queried")
    time_period: Dict[str, str] = Field(default_factory=dict, description="Time period queried")
    is_mock_data: bool = Field(default=False, description="Whether this is mock data")
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# Helper Functions
# =============================================================================

def _get_time_period_dates(time_period: TimePeriod) -> tuple:
    """Convert TimePeriod enum to actual date range."""
    today = datetime.now().date()
    
    if time_period == TimePeriod.LAST_7_DAYS:
        from_date = today - timedelta(days=7)
    elif time_period == TimePeriod.LAST_30_DAYS:
        from_date = today - timedelta(days=30)
    elif time_period == TimePeriod.MONTH_TO_DATE:
        from_date = today.replace(day=1)
    else:
        from_date = today - timedelta(days=30)
    
    return from_date.isoformat(), today.isoformat()


def _generate_mock_cost_data(
    subscription_id: str,
    resource_group: Optional[str],
    time_period: TimePeriod
) -> AzureCostOutput:
    """Generate mock cost data for fallback when API fails.
    
    Used as fallback or when Cost Management SDK is not available.
    """
    # Mock breakdown data
    if resource_group:
        breakdown = [
            CostBreakdownItem(name="Virtual Machines", cost=145.23),
            CostBreakdownItem(name="Storage", cost=32.10),
            CostBreakdownItem(name="Networking", cost=18.45),
            CostBreakdownItem(name="App Service", cost=89.00),
        ]
        total = sum(item.cost for item in breakdown)
    else:
        breakdown = [
            CostBreakdownItem(name="rg-production", cost=523.45),
            CostBreakdownItem(name="rg-staging", cost=156.78),
            CostBreakdownItem(name="rg-development", cost=89.12),
            CostBreakdownItem(name="rg-shared", cost=234.56),
        ]
        total = sum(item.cost for item in breakdown)

    multiplier = {
        TimePeriod.LAST_7_DAYS: 0.25,
        TimePeriod.LAST_30_DAYS: 1.0,
        TimePeriod.MONTH_TO_DATE: 0.75,
    }.get(time_period, 1.0)

    return AzureCostOutput(
        success=True,
        total_cost=round(total * multiplier, 2),
        currency="USD",
        breakdown=[
            CostBreakdownItem(
                name=item.name,
                cost=round(item.cost * multiplier, 2)
            )
            for item in breakdown
        ],
        time_period=time_period.value,
        is_mock_data=True
    )


# =============================================================================
# Tool Implementations
# =============================================================================

async def azure_cost_get_summary(params: AzureCostInput) -> AzureCostOutput:
    """Get Azure cost summary.

    Uses Azure Cost Management API to retrieve cost data.
    Falls back to mock data if API is not available.

    Args:
        params: Validated input parameters

    Returns:
        Cost summary with breakdown
    """
    logger.info(
        f"azure_cost_get_summary called: subscription_id={params.subscription_id}, "
        f"resource_group={params.resource_group}, time_period={params.time_period.value}"
    )

    try:
        from azure.mgmt.costmanagement import CostManagementClient
        from azure.mgmt.costmanagement.models import (
            QueryDefinition,
            QueryDataset,
            QueryAggregation,
            QueryGrouping,
            QueryTimePeriod,
            ExportType,
            TimeframeType,
        )
        
        credential, subscription_id = get_credential_and_subscription(params.subscription_id)
        client = CostManagementClient(credential)
        
        # Build scope
        if params.resource_group:
            scope = f"/subscriptions/{subscription_id}/resourceGroups/{params.resource_group}"
            grouping = [QueryGrouping(type="Dimension", name="ServiceName")]
        else:
            scope = f"/subscriptions/{subscription_id}"
            grouping = [QueryGrouping(type="Dimension", name="ResourceGroup")]
        
        # Get date range
        from_date, to_date = _get_time_period_dates(params.time_period)
        
        # Build query
        query = QueryDefinition(
            type=ExportType.ACTUAL_COST,
            timeframe=TimeframeType.CUSTOM,
            time_period=QueryTimePeriod(
                from_property=datetime.fromisoformat(from_date),
                to=datetime.fromisoformat(to_date),
            ),
            dataset=QueryDataset(
                granularity="None",
                aggregation={
                    "totalCost": QueryAggregation(name="Cost", function="Sum")
                },
                grouping=grouping,
            ),
        )
        
        # Execute query
        result = client.query.usage(scope, query)
        
        # Parse results
        breakdown = []
        total_cost = 0.0
        currency = "USD"
        
        if result.rows:
            for row in result.rows:
                # Row format: [cost, name, currency]
                if len(row) >= 2:
                    cost = float(row[0]) if row[0] else 0.0
                    name = str(row[1]) if len(row) > 1 else "Unknown"
                    if len(row) > 2:
                        currency = str(row[2])
                    
                    breakdown.append(CostBreakdownItem(name=name, cost=round(cost, 2)))
                    total_cost += cost
        
        # Sort by cost descending
        breakdown.sort(key=lambda x: x.cost, reverse=True)
        
        logger.info(f"Retrieved cost data: total={total_cost:.2f} {currency}")
        
        return AzureCostOutput(
            success=True,
            total_cost=round(total_cost, 2),
            currency=currency,
            breakdown=breakdown,
            time_period=params.time_period.value,
            is_mock_data=False,
        )
        
    except ImportError:
        logger.warning("azure-mgmt-costmanagement not installed, using mock data")
        return _generate_mock_cost_data(
            params.subscription_id,
            params.resource_group,
            params.time_period
        )
    except AzureError as e:
        logger.error(f"Azure error getting cost summary: {e}")
        return AzureCostOutput(
            success=False,
            total_cost=0.0,
            currency="USD",
            breakdown=[],
            time_period=params.time_period.value,
            is_mock_data=False,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get cost summary, falling back to mock data: {e}")
        # Fall back to mock data on error
        return _generate_mock_cost_data(
            params.subscription_id,
            params.resource_group,
            params.time_period
        )


async def azure_cost_get_top_cost_drivers(
    params: AzureCostGetTopCostDriversInput
) -> AzureCostGetTopCostDriversOutput:
    """Get top cost drivers for a scope.

    Args:
        params.scope: Cost scope (subscription or resource group)
        params.time_period: Time period with from/to dates
        params.top_n: Number of top drivers to return
        params.group_by: Grouping dimension

    Returns:
        Top cost drivers sorted by cost
    """
    logger.info(f"Getting top {params.top_n} cost drivers for scope: {params.scope}")
    
    try:
        from azure.mgmt.costmanagement import CostManagementClient
        from azure.mgmt.costmanagement.models import (
            QueryDefinition,
            QueryDataset,
            QueryAggregation,
            QueryGrouping,
            QueryTimePeriod,
            ExportType,
            TimeframeType,
        )
        
        # Extract subscription from scope
        scope_parts = params.scope.strip("/").split("/")
        subscription_id = None
        for i, part in enumerate(scope_parts):
            if part.lower() == "subscriptions" and i + 1 < len(scope_parts):
                subscription_id = scope_parts[i + 1]
                break
        
        if not subscription_id:
            return AzureCostGetTopCostDriversOutput(
                success=False,
                scope=params.scope,
                error="Could not extract subscription ID from scope",
            )
        
        credential, _ = get_credential_and_subscription(subscription_id)
        client = CostManagementClient(credential)
        
        # Parse dates
        from_date = datetime.fromisoformat(params.time_period.get("from", ""))
        to_date = datetime.fromisoformat(params.time_period.get("to", ""))
        
        # Map group_by to dimension name
        dimension_map = {
            "ResourceGroup": "ResourceGroup",
            "ServiceName": "ServiceName",
            "ResourceType": "ResourceType",
            "ResourceId": "ResourceId",
        }
        dimension = dimension_map.get(params.group_by, "ResourceGroup")
        
        # Build query
        query = QueryDefinition(
            type=ExportType.ACTUAL_COST,
            timeframe=TimeframeType.CUSTOM,
            time_period=QueryTimePeriod(
                from_property=from_date,
                to=to_date,
            ),
            dataset=QueryDataset(
                granularity="None",
                aggregation={
                    "totalCost": QueryAggregation(name="Cost", function="Sum")
                },
                grouping=[QueryGrouping(type="Dimension", name=dimension)],
            ),
        )
        
        # Execute query
        result = client.query.usage(params.scope, query)
        
        # Parse results
        cost_drivers = []
        total_cost = 0.0
        currency = "USD"
        
        if result.rows:
            for row in result.rows:
                if len(row) >= 2:
                    cost = float(row[0]) if row[0] else 0.0
                    name = str(row[1]) if len(row) > 1 else "Unknown"
                    if len(row) > 2:
                        currency = str(row[2])
                    
                    cost_drivers.append(CostDriver(
                        name=name,
                        cost=round(cost, 2),
                        currency=currency,
                    ))
                    total_cost += cost
        
        # Sort by cost descending and take top N
        cost_drivers.sort(key=lambda x: x.cost, reverse=True)
        cost_drivers = cost_drivers[:params.top_n]
        
        # Calculate percentages
        for driver in cost_drivers:
            if total_cost > 0:
                driver.percentage = round((driver.cost / total_cost) * 100, 2)
        
        logger.info(f"Found {len(cost_drivers)} cost drivers, total: {total_cost:.2f}")
        
        return AzureCostGetTopCostDriversOutput(
            success=True,
            cost_drivers=cost_drivers,
            total_cost=round(total_cost, 2),
            currency=currency,
            scope=params.scope,
            time_period=params.time_period,
            is_mock_data=False,
        )
        
    except ImportError:
        logger.warning("azure-mgmt-costmanagement not installed")
        # Return mock data
        mock_drivers = [
            CostDriver(name="rg-production", cost=523.45, currency="USD", percentage=52.1),
            CostDriver(name="rg-staging", cost=234.56, currency="USD", percentage=23.4),
            CostDriver(name="rg-development", cost=156.78, currency="USD", percentage=15.6),
            CostDriver(name="rg-shared", cost=89.12, currency="USD", percentage=8.9),
        ]
        return AzureCostGetTopCostDriversOutput(
            success=True,
            cost_drivers=mock_drivers[:params.top_n],
            total_cost=sum(d.cost for d in mock_drivers),
            currency="USD",
            scope=params.scope,
            time_period=params.time_period,
            is_mock_data=True,
        )
    except AzureError as e:
        logger.error(f"Azure error getting top cost drivers: {e}")
        return AzureCostGetTopCostDriversOutput(
            success=False,
            scope=params.scope,
            time_period=params.time_period,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get top cost drivers: {e}")
        wrapped = wrap_azure_error(e)
        return AzureCostGetTopCostDriversOutput(
            success=False,
            scope=params.scope,
            time_period=params.time_period,
            error=wrapped.message,
        )
