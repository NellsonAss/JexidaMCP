"""Azure Cost tool implementation.

Provides the azure_cost.get_summary tool for retrieving cost summaries.

NOTE: This is currently a stub implementation returning mock data.
TODO: Implement real Azure Cost Management API integration.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from logging_config import get_logger, ToolInvocationLogger
from tool_registry import tool

from .utils import validate_subscription_id

logger = get_logger(__name__)


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
    """Input schema for azure_cost.get_summary tool."""
    
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
    """Output schema for azure_cost.get_summary tool."""
    
    total_cost: float = Field(
        description="Total cost for the period"
    )
    currency: str = Field(
        description="Currency code (e.g., USD, EUR)"
    )
    breakdown: List[CostBreakdownItem] = Field(
        description="Cost breakdown by resource group or service"
    )
    time_period: str = Field(
        description="The time period queried"
    )
    is_mock_data: bool = Field(
        default=True,
        description="Indicates if this is mock/stub data"
    )


def _generate_mock_cost_data(
    subscription_id: str,
    resource_group: Optional[str],
    time_period: TimePeriod
) -> AzureCostOutput:
    """Generate mock cost data for development/testing.
    
    TODO: Replace this with real Azure Cost Management API calls.
    
    The real implementation should:
    1. Use Azure Cost Management REST API or SDK
    2. Query costs for the specified subscription and time period
    3. Aggregate by resource group or service
    4. Return actual cost data
    
    Azure Cost Management API reference:
    https://learn.microsoft.com/en-us/rest/api/cost-management/
    
    Args:
        subscription_id: Azure subscription ID
        resource_group: Optional resource group filter
        time_period: Time period for the query
        
    Returns:
        Mock cost data
    """
    # Mock breakdown data
    if resource_group:
        # If filtering by resource group, return service-level breakdown
        breakdown = [
            CostBreakdownItem(name="Virtual Machines", cost=145.23),
            CostBreakdownItem(name="Storage", cost=32.10),
            CostBreakdownItem(name="Networking", cost=18.45),
            CostBreakdownItem(name="App Service", cost=89.00),
        ]
        total = sum(item.cost for item in breakdown)
    else:
        # Return resource group breakdown
        breakdown = [
            CostBreakdownItem(name="rg-production", cost=523.45),
            CostBreakdownItem(name="rg-staging", cost=156.78),
            CostBreakdownItem(name="rg-development", cost=89.12),
            CostBreakdownItem(name="rg-shared", cost=234.56),
        ]
        total = sum(item.cost for item in breakdown)
    
    # Adjust based on time period
    multiplier = {
        TimePeriod.LAST_7_DAYS: 0.25,
        TimePeriod.LAST_30_DAYS: 1.0,
        TimePeriod.MONTH_TO_DATE: 0.75,
    }.get(time_period, 1.0)
    
    return AzureCostOutput(
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


@tool(
    name="azure_cost.get_summary",
    description="Get Azure cost summary for a subscription or resource group",
    input_schema=AzureCostInput,
    output_schema=AzureCostOutput,
    tags=["azure", "cost", "billing"]
)
async def get_cost_summary(params: AzureCostInput) -> AzureCostOutput:
    """Get Azure cost summary.
    
    NOTE: Currently returns mock data. See _generate_mock_cost_data for
    implementation notes on integrating with Azure Cost Management API.
    
    Args:
        params: Validated input parameters
        
    Returns:
        Cost summary with breakdown
    """
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start(
        "azure_cost.get_summary",
        subscription_id=params.subscription_id,
        resource_group=params.resource_group,
        time_period=params.time_period.value
    )
    
    try:
        # TODO: Implement real Azure Cost Management API call here
        # 
        # Example implementation steps:
        # 1. Get access token using Azure SDK or CLI
        # 2. Call Cost Management Query API:
        #    POST https://management.azure.com/subscriptions/{subscriptionId}/providers/Microsoft.CostManagement/query?api-version=2023-03-01
        # 3. Parse response and aggregate costs
        # 4. Handle pagination for large result sets
        #
        # For now, return mock data
        
        result = _generate_mock_cost_data(
            params.subscription_id,
            params.resource_group,
            params.time_period
        )
        
        invocation_logger.success(
            total_cost=result.total_cost,
            currency=result.currency,
            breakdown_count=len(result.breakdown)
        )
        
        return result
        
    except Exception as e:
        invocation_logger.failure(f"Failed to get cost summary: {str(e)}")
        raise

