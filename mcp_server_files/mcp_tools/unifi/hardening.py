"""Network hardening plan application tool.

Provides the network_apply_hardening_plan tool for applying security
recommendations in a controlled, phased manner.
"""

import asyncio
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from logging_config import get_logger, ToolInvocationLogger
from tool_registry import tool

from .changes import (
    FirewallEdit,
    UpnpEdit,
    VlanEdit,
    WifiEdit,
    unifi_apply_changes,
    UniFiApplyChangesInput,
)
from .client import UniFiClient, UniFiConnectionError, UniFiAuthError, UniFiAPIError

logger = get_logger(__name__)


# Phase definitions
PHASE_DESCRIPTIONS = {
    1: "Low-risk changes (UPnP, unused SSIDs, client isolation)",
    2: "Firewall rule changes",
    3: "VLAN and network segmentation changes",
}


# -------------------------------------------------------------------------
# Input/Output Models
# -------------------------------------------------------------------------

class RecommendedChange(BaseModel):
    """A recommended change from the audit."""
    category: str = Field(description="Change category: wifi, firewall, vlan, upnp")
    change_type: str = Field(description="Type of change: update, create, delete")
    target: str = Field(description="Target name/ID")
    changes: Dict[str, Any] = Field(description="The changes to apply")
    finding_ids: List[str] = Field(default_factory=list, description="Related finding IDs")
    phase: int = Field(default=1, description="Phase number for phased rollout")


class HardeningPlan(BaseModel):
    """A hardening plan from the audit."""
    changes: List[RecommendedChange] = Field(
        default_factory=list,
        description="List of recommended changes"
    )


class NetworkApplyHardeningPlanInput(BaseModel):
    """Input schema for network_apply_hardening_plan tool."""
    
    plan: HardeningPlan = Field(
        description="Hardening plan from network_hardening_audit recommended_changes"
    )
    confirm: bool = Field(
        default=False,
        description="Set to true to actually apply changes (false for preview)"
    )
    phased: bool = Field(
        default=True,
        description="Apply changes in phases (true) or all at once (false)"
    )
    site_id: Optional[str] = Field(
        default=None,
        description="UniFi site ID (defaults to configured site)"
    )
    stop_on_failure: bool = Field(
        default=True,
        description="Stop if a phase fails (only relevant when phased=true)"
    )


class PhaseResult(BaseModel):
    """Result of applying a single phase."""
    phase: int = Field(description="Phase number")
    description: str = Field(description="Phase description")
    changes_count: int = Field(description="Number of changes in this phase")
    applied: bool = Field(description="Whether phase was applied")
    success: bool = Field(description="Whether phase succeeded")
    changes_applied: int = Field(default=0, description="Changes successfully applied")
    changes_failed: int = Field(default=0, description="Changes that failed")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    connectivity_check: Optional[bool] = Field(
        default=None,
        description="Whether connectivity check passed after phase"
    )


class NetworkApplyHardeningPlanOutput(BaseModel):
    """Output schema for network_apply_hardening_plan tool."""
    
    success: bool = Field(description="Whether overall operation succeeded")
    preview_only: bool = Field(description="Whether this was a preview (confirm=false)")
    phases: List[PhaseResult] = Field(
        default_factory=list,
        description="Results for each phase"
    )
    total_changes: int = Field(default=0, description="Total changes in plan")
    total_applied: int = Field(default=0, description="Total changes applied")
    total_failed: int = Field(default=0, description="Total changes failed")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    error: str = Field(default="", description="Error message if failed")


def group_changes_by_phase(changes: List[RecommendedChange]) -> Dict[int, List[RecommendedChange]]:
    """Group changes by their phase number.
    
    Args:
        changes: List of recommended changes
        
    Returns:
        Dictionary mapping phase number to list of changes
    """
    phases: Dict[int, List[RecommendedChange]] = {}
    
    for change in changes:
        phase = change.phase
        if phase not in phases:
            phases[phase] = []
        phases[phase].append(change)
    
    return phases


def convert_to_edits(changes: List[RecommendedChange]) -> tuple[
    List[WifiEdit],
    List[FirewallEdit],
    List[VlanEdit],
    Optional[UpnpEdit],
]:
    """Convert recommended changes to edit objects.
    
    Args:
        changes: List of recommended changes
        
    Returns:
        Tuple of (wifi_edits, firewall_edits, vlan_edits, upnp_edits)
    """
    wifi_edits = []
    firewall_edits = []
    vlan_edits = []
    upnp_edit = None
    
    for change in changes:
        if change.category == "wifi":
            wifi_edits.append(WifiEdit(**change.changes))
        elif change.category == "firewall":
            firewall_edits.append(FirewallEdit(
                action=change.change_type,
                **change.changes,
            ))
        elif change.category == "vlan":
            vlan_edits.append(VlanEdit(
                action=change.change_type,
                **change.changes,
            ))
        elif change.category == "upnp":
            # Merge UPnP changes
            if upnp_edit is None:
                upnp_edit = UpnpEdit(**change.changes)
            else:
                # Update existing edit with new values
                current = upnp_edit.model_dump(exclude_none=True)
                current.update(change.changes)
                upnp_edit = UpnpEdit(**current)
    
    return wifi_edits, firewall_edits, vlan_edits, upnp_edit


async def check_connectivity(client: UniFiClient) -> bool:
    """Basic connectivity check after applying changes.
    
    Verifies we can still communicate with the controller.
    
    Args:
        client: UniFi client instance
        
    Returns:
        True if connectivity check passes
    """
    try:
        # Try to list devices as a basic connectivity test
        await client.get_devices()
        return True
    except Exception:
        return False


@tool(
    name="network_apply_hardening_plan",
    description="Apply a hardening plan from the security audit in controlled phases",
    input_schema=NetworkApplyHardeningPlanInput,
    output_schema=NetworkApplyHardeningPlanOutput,
    tags=["unifi", "network", "security", "hardening"]
)
async def network_apply_hardening_plan(
    params: NetworkApplyHardeningPlanInput
) -> NetworkApplyHardeningPlanOutput:
    """Apply hardening plan in controlled phases.
    
    If confirm=False, returns a preview of what would be changed.
    If confirm=True, applies changes phase by phase with connectivity checks.
    
    Args:
        params: Plan application parameters
        
    Returns:
        Results of plan application
    """
    invocation_logger = ToolInvocationLogger(logger)
    invocation_logger.start(
        "network_apply_hardening_plan",
        confirm=params.confirm,
        phased=params.phased,
        total_changes=len(params.plan.changes),
    )
    
    warnings = []
    
    try:
        # Group changes by phase
        phases_dict = group_changes_by_phase(params.plan.changes)
        
        if not phases_dict:
            return NetworkApplyHardeningPlanOutput(
                success=True,
                preview_only=not params.confirm,
                phases=[],
                total_changes=0,
                warnings=["No changes in plan"],
            )
        
        # Sort phases
        phase_numbers = sorted(phases_dict.keys())
        
        # Build phase results for preview
        phase_results = []
        
        for phase_num in phase_numbers:
            phase_changes = phases_dict[phase_num]
            phase_results.append(PhaseResult(
                phase=phase_num,
                description=PHASE_DESCRIPTIONS.get(phase_num, f"Phase {phase_num}"),
                changes_count=len(phase_changes),
                applied=False,
                success=False,
            ))
        
        total_changes = len(params.plan.changes)
        
        # If not confirmed, return preview
        if not params.confirm:
            invocation_logger.success(preview_only=True)
            return NetworkApplyHardeningPlanOutput(
                success=True,
                preview_only=True,
                phases=phase_results,
                total_changes=total_changes,
                warnings=["This is a preview. Set confirm=true to apply changes."],
            )
        
        # Apply changes
        total_applied = 0
        total_failed = 0
        updated_results = []
        
        async with UniFiClient(site=params.site_id) as client:
            if params.phased:
                # Apply phase by phase
                for phase_num in phase_numbers:
                    phase_changes = phases_dict[phase_num]
                    
                    # Convert to edits
                    wifi_edits, firewall_edits, vlan_edits, upnp_edit = convert_to_edits(phase_changes)
                    
                    # Apply changes for this phase
                    apply_input = UniFiApplyChangesInput(
                        dry_run=False,
                        site_id=params.site_id,
                        wifi_edits=wifi_edits,
                        firewall_edits=firewall_edits,
                        vlan_edits=vlan_edits,
                        upnp_edits=upnp_edit,
                    )
                    
                    apply_result = await unifi_apply_changes(apply_input)
                    
                    # Check connectivity after phase
                    connectivity_ok = await check_connectivity(client)
                    
                    phase_result = PhaseResult(
                        phase=phase_num,
                        description=PHASE_DESCRIPTIONS.get(phase_num, f"Phase {phase_num}"),
                        changes_count=len(phase_changes),
                        applied=True,
                        success=apply_result.success and connectivity_ok,
                        changes_applied=apply_result.changes_applied,
                        changes_failed=apply_result.changes_failed,
                        errors=apply_result.warnings,
                        connectivity_check=connectivity_ok,
                    )
                    
                    updated_results.append(phase_result)
                    total_applied += apply_result.changes_applied
                    total_failed += apply_result.changes_failed
                    
                    if not phase_result.success:
                        if not connectivity_ok:
                            warnings.append(f"Phase {phase_num} may have caused connectivity issues")
                        
                        if params.stop_on_failure:
                            warnings.append(f"Stopped after phase {phase_num} due to failure")
                            # Add remaining phases as not applied
                            for remaining_phase in phase_numbers[phase_numbers.index(phase_num) + 1:]:
                                remaining_changes = phases_dict[remaining_phase]
                                updated_results.append(PhaseResult(
                                    phase=remaining_phase,
                                    description=PHASE_DESCRIPTIONS.get(remaining_phase, f"Phase {remaining_phase}"),
                                    changes_count=len(remaining_changes),
                                    applied=False,
                                    success=False,
                                    errors=["Skipped due to previous phase failure"],
                                ))
                            break
                    
                    # Small delay between phases
                    await asyncio.sleep(1)
            else:
                # Apply all at once
                all_changes = params.plan.changes
                wifi_edits, firewall_edits, vlan_edits, upnp_edit = convert_to_edits(all_changes)
                
                apply_input = UniFiApplyChangesInput(
                    dry_run=False,
                    site_id=params.site_id,
                    wifi_edits=wifi_edits,
                    firewall_edits=firewall_edits,
                    vlan_edits=vlan_edits,
                    upnp_edits=upnp_edit,
                )
                
                apply_result = await unifi_apply_changes(apply_input)
                
                connectivity_ok = await check_connectivity(client)
                
                # Create single phase result for all changes
                updated_results.append(PhaseResult(
                    phase=0,
                    description="All changes (non-phased)",
                    changes_count=len(all_changes),
                    applied=True,
                    success=apply_result.success and connectivity_ok,
                    changes_applied=apply_result.changes_applied,
                    changes_failed=apply_result.changes_failed,
                    errors=apply_result.warnings,
                    connectivity_check=connectivity_ok,
                ))
                
                total_applied = apply_result.changes_applied
                total_failed = apply_result.changes_failed
        
        overall_success = total_failed == 0
        
        if overall_success:
            invocation_logger.success(
                total_applied=total_applied,
                total_failed=total_failed,
            )
        else:
            invocation_logger.failure(
                f"{total_failed} change(s) failed",
                total_applied=total_applied,
            )
        
        return NetworkApplyHardeningPlanOutput(
            success=overall_success,
            preview_only=False,
            phases=updated_results,
            total_changes=total_changes,
            total_applied=total_applied,
            total_failed=total_failed,
            warnings=warnings,
        )
        
    except UniFiConnectionError as e:
        invocation_logger.failure(str(e))
        return NetworkApplyHardeningPlanOutput(
            success=False,
            preview_only=not params.confirm,
            error=f"Connection error: {e}",
        )
    except UniFiAuthError as e:
        invocation_logger.failure(str(e))
        return NetworkApplyHardeningPlanOutput(
            success=False,
            preview_only=not params.confirm,
            error=f"Authentication error: {e}",
        )
    except UniFiAPIError as e:
        invocation_logger.failure(str(e))
        return NetworkApplyHardeningPlanOutput(
            success=False,
            preview_only=not params.confirm,
            error=f"API error: {e}",
        )
    except Exception as e:
        invocation_logger.failure(f"Unexpected error: {e}")
        return NetworkApplyHardeningPlanOutput(
            success=False,
            preview_only=not params.confirm,
            error=f"Unexpected error: {e}",
        )

