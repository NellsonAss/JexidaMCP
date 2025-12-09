"""Tests for azure_cost.get_summary tool."""

import pytest

from mcp_tools.azure.cost import (
    AzureCostInput,
    AzureCostOutput,
    CostBreakdownItem,
    TimePeriod,
    get_cost_summary,
)


class TestAzureCostInput:
    """Tests for AzureCostInput schema validation."""
    
    def test_valid_input_minimal(self):
        """Test valid minimal input."""
        input_data = AzureCostInput(
            subscription_id="12345678-1234-1234-1234-123456789abc"
        )
        assert input_data.subscription_id == "12345678-1234-1234-1234-123456789abc"
        assert input_data.resource_group is None
        assert input_data.time_period == TimePeriod.LAST_30_DAYS
    
    def test_valid_input_full(self):
        """Test valid full input."""
        input_data = AzureCostInput(
            subscription_id="12345678-1234-1234-1234-123456789abc",
            resource_group="my-resource-group",
            time_period=TimePeriod.LAST_7_DAYS
        )
        assert input_data.resource_group == "my-resource-group"
        assert input_data.time_period == TimePeriod.LAST_7_DAYS
    
    def test_invalid_subscription_rejected(self):
        """Test invalid subscription ID is rejected."""
        with pytest.raises(ValueError, match="Invalid subscription ID"):
            AzureCostInput(subscription_id="not-valid")
    
    def test_time_period_enum_values(self):
        """Test all time period enum values."""
        for period in TimePeriod:
            input_data = AzureCostInput(
                subscription_id="12345678-1234-1234-1234-123456789abc",
                time_period=period
            )
            assert input_data.time_period == period


class TestAzureCostOutput:
    """Tests for AzureCostOutput schema."""
    
    def test_output_structure(self):
        """Test output has correct structure."""
        output = AzureCostOutput(
            total_cost=123.45,
            currency="USD",
            breakdown=[
                CostBreakdownItem(name="rg-test", cost=100.00),
                CostBreakdownItem(name="rg-dev", cost=23.45),
            ],
            time_period="Last30Days",
            is_mock_data=True
        )
        
        assert output.total_cost == 123.45
        assert output.currency == "USD"
        assert len(output.breakdown) == 2
        assert output.breakdown[0].name == "rg-test"
        assert output.is_mock_data is True


class TestGetCostSummary:
    """Tests for get_cost_summary function."""
    
    @pytest.mark.asyncio
    async def test_returns_mock_data(self):
        """Test that function returns mock data."""
        params = AzureCostInput(
            subscription_id="12345678-1234-1234-1234-123456789abc"
        )
        
        result = await get_cost_summary(params)
        
        assert result.is_mock_data is True
        assert result.total_cost > 0
        assert result.currency == "USD"
        assert len(result.breakdown) > 0
    
    @pytest.mark.asyncio
    async def test_resource_group_filter(self):
        """Test filtering by resource group returns different breakdown."""
        params_no_rg = AzureCostInput(
            subscription_id="12345678-1234-1234-1234-123456789abc"
        )
        params_with_rg = AzureCostInput(
            subscription_id="12345678-1234-1234-1234-123456789abc",
            resource_group="my-rg"
        )
        
        result_no_rg = await get_cost_summary(params_no_rg)
        result_with_rg = await get_cost_summary(params_with_rg)
        
        # Both should return data
        assert len(result_no_rg.breakdown) > 0
        assert len(result_with_rg.breakdown) > 0
        
        # With RG filter, breakdown should be service-level (different names)
        no_rg_names = [item.name for item in result_no_rg.breakdown]
        with_rg_names = [item.name for item in result_with_rg.breakdown]
        
        # Check that at least one name differs (mock data returns different breakdowns)
        assert no_rg_names != with_rg_names
    
    @pytest.mark.asyncio
    async def test_time_period_affects_costs(self):
        """Test that different time periods return different costs."""
        params_7_days = AzureCostInput(
            subscription_id="12345678-1234-1234-1234-123456789abc",
            time_period=TimePeriod.LAST_7_DAYS
        )
        params_30_days = AzureCostInput(
            subscription_id="12345678-1234-1234-1234-123456789abc",
            time_period=TimePeriod.LAST_30_DAYS
        )
        
        result_7_days = await get_cost_summary(params_7_days)
        result_30_days = await get_cost_summary(params_30_days)
        
        # 7 days should be less than 30 days (mock applies multiplier)
        assert result_7_days.total_cost < result_30_days.total_cost
    
    @pytest.mark.asyncio
    async def test_breakdown_sums_to_total(self):
        """Test that breakdown costs sum approximately to total."""
        params = AzureCostInput(
            subscription_id="12345678-1234-1234-1234-123456789abc"
        )
        
        result = await get_cost_summary(params)
        
        breakdown_sum = sum(item.cost for item in result.breakdown)
        # Allow small floating point difference
        assert abs(result.total_cost - breakdown_sum) < 0.01

