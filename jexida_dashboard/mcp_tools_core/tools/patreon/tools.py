"""MCP tools for Patreon API.

Provides async tool functions for:
- Getting creator/campaign info
- Listing tiers
- Listing and filtering patrons
- Exporting patron data
"""

import csv
import io
import logging
from typing import Optional, List

from pydantic import BaseModel, Field

from .client import (
    PatreonClient,
    PatreonConfig,
    PatreonError,
    PatreonConfigError,
    get_default_campaign_id,
    validate_patreon_config,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Input/Output Schemas
# =============================================================================

class PatreonGetCreatorInput(BaseModel):
    """Input schema for patreon_get_creator."""
    pass  # No parameters needed


class CampaignInfo(BaseModel):
    """Campaign information."""
    id: str = Field(description="Campaign ID")
    name: str = Field(default="", description="Campaign name")
    patron_count: int = Field(default=0, description="Number of patrons")
    url: str = Field(default="", description="Campaign URL")
    summary: str = Field(default="", description="Campaign summary")
    is_monthly: bool = Field(default=True, description="Whether campaign uses monthly billing")


class PatreonGetCreatorOutput(BaseModel):
    """Output schema for patreon_get_creator."""
    success: bool = Field(description="Whether the request succeeded")
    creator_id: str = Field(default="", description="Creator user ID")
    creator_name: str = Field(default="", description="Creator full name")
    creator_email: str = Field(default="", description="Creator email")
    campaign: Optional[CampaignInfo] = Field(default=None, description="Primary campaign info")
    error: str = Field(default="", description="Error message if failed")


class PatreonGetTiersInput(BaseModel):
    """Input schema for patreon_get_tiers."""
    campaign_id: Optional[str] = Field(
        default=None,
        description="Campaign ID (uses default from env if not provided)"
    )


class TierInfo(BaseModel):
    """Tier information."""
    id: str = Field(description="Tier ID")
    title: str = Field(default="", description="Tier title/name")
    amount_cents: int = Field(default=0, description="Tier price in cents")
    description: str = Field(default="", description="Tier description")
    patron_count: int = Field(default=0, description="Number of patrons at this tier")
    published: bool = Field(default=True, description="Whether tier is published")


class PatreonGetTiersOutput(BaseModel):
    """Output schema for patreon_get_tiers."""
    success: bool = Field(description="Whether the request succeeded")
    campaign_id: str = Field(default="", description="Campaign ID")
    tiers: List[TierInfo] = Field(default_factory=list, description="List of tiers")
    count: int = Field(default=0, description="Number of tiers")
    error: str = Field(default="", description="Error message if failed")


class PatreonGetPatronsInput(BaseModel):
    """Input schema for patreon_get_patrons."""
    campaign_id: Optional[str] = Field(
        default=None,
        description="Campaign ID (uses default from env if not provided)"
    )
    status_filter: Optional[str] = Field(
        default=None,
        description="Filter by patron status: active_patron, declined_patron, former_patron"
    )
    tier_filter: Optional[str] = Field(
        default=None,
        description="Filter by tier title (case-insensitive partial match)"
    )


class PatronInfo(BaseModel):
    """Patron information."""
    id: str = Field(description="Member ID")
    full_name: str = Field(default="", description="Patron's full name")
    email: str = Field(default="", description="Patron's email")
    patron_status: str = Field(default="", description="Status: active_patron, declined_patron, former_patron")
    lifetime_support_cents: int = Field(default=0, description="Lifetime support in cents")
    currently_entitled_amount_cents: int = Field(default=0, description="Current pledge in cents")
    last_charge_date: Optional[str] = Field(default=None, description="Last charge date")
    last_charge_status: Optional[str] = Field(default=None, description="Last charge status")
    pledge_start: Optional[str] = Field(default=None, description="When they started pledging")
    tier_id: str = Field(default="", description="Current tier ID")
    tier_name: str = Field(default="", description="Current tier name")


class PatreonGetPatronsOutput(BaseModel):
    """Output schema for patreon_get_patrons."""
    success: bool = Field(description="Whether the request succeeded")
    campaign_id: str = Field(default="", description="Campaign ID")
    patrons: List[PatronInfo] = Field(default_factory=list, description="List of patrons")
    count: int = Field(default=0, description="Number of patrons")
    total_monthly_cents: int = Field(default=0, description="Total monthly pledge in cents")
    error: str = Field(default="", description="Error message if failed")


class PatreonGetPatronInput(BaseModel):
    """Input schema for patreon_get_patron."""
    patron_id: str = Field(description="The patron/member ID to look up")


class PatreonGetPatronOutput(BaseModel):
    """Output schema for patreon_get_patron."""
    success: bool = Field(description="Whether the request succeeded")
    patron: Optional[PatronInfo] = Field(default=None, description="Patron details")
    error: str = Field(default="", description="Error message if failed")


class PatreonExportPatronsInput(BaseModel):
    """Input schema for patreon_export_patrons."""
    campaign_id: Optional[str] = Field(
        default=None,
        description="Campaign ID (uses default from env if not provided)"
    )
    status_filter: Optional[str] = Field(
        default=None,
        description="Filter by patron status"
    )
    format: str = Field(
        default="json",
        description="Export format: json or csv"
    )


class PatreonExportPatronsOutput(BaseModel):
    """Output schema for patreon_export_patrons."""
    success: bool = Field(description="Whether the export succeeded")
    format: str = Field(default="json", description="Export format used")
    data: str = Field(default="", description="Exported data (JSON string or CSV)")
    count: int = Field(default=0, description="Number of patrons exported")
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# Tool Implementations
# =============================================================================

async def patreon_get_creator(
    params: PatreonGetCreatorInput
) -> PatreonGetCreatorOutput:
    """Get creator and campaign information.
    
    Returns the authenticated creator's info and their primary campaign details.
    
    Returns:
        Creator info with primary campaign
    """
    logger.info("Getting Patreon creator info")
    
    try:
        async with PatreonClient() as client:
            # Get identity with campaign
            identity_data = await client.get_identity()
            
            user = identity_data.get("data", {})
            user_attrs = user.get("attributes", {})
            
            # Get campaign from included data
            campaign = None
            included = identity_data.get("included", [])
            for item in included:
                if item.get("type") == "campaign":
                    campaign_attrs = item.get("attributes", {})
                    campaign = CampaignInfo(
                        id=item.get("id", ""),
                        name=campaign_attrs.get("creation_name", ""),
                        patron_count=campaign_attrs.get("patron_count", 0),
                        url=campaign_attrs.get("url", ""),
                        summary=campaign_attrs.get("summary", ""),
                        is_monthly=campaign_attrs.get("is_monthly", True),
                    )
                    break
            
            return PatreonGetCreatorOutput(
                success=True,
                creator_id=user.get("id", ""),
                creator_name=user_attrs.get("full_name", ""),
                creator_email=user_attrs.get("email", ""),
                campaign=campaign,
            )
            
    except PatreonError as e:
        logger.error(f"Patreon error getting creator: {e}")
        return PatreonGetCreatorOutput(
            success=False,
            error=e.message,
        )
    except Exception as e:
        logger.error(f"Failed to get creator info: {e}")
        return PatreonGetCreatorOutput(
            success=False,
            error=str(e),
        )


async def patreon_get_tiers(
    params: PatreonGetTiersInput
) -> PatreonGetTiersOutput:
    """Get tiers for a campaign.
    
    Args:
        params.campaign_id: Campaign ID (uses default from env if not provided)
        
    Returns:
        List of tiers with details
    """
    campaign_id = params.campaign_id or get_default_campaign_id()
    
    if not campaign_id:
        return PatreonGetTiersOutput(
            success=False,
            error="No campaign_id provided and PATREON_CREATOR_CAMPAIGN_ID not set",
        )
    
    logger.info(f"Getting Patreon tiers for campaign: {campaign_id}")
    
    try:
        async with PatreonClient() as client:
            tiers_data = await client.get_tiers(campaign_id)
            
            tiers = [
                TierInfo(
                    id=t.get("id", ""),
                    title=t.get("title", ""),
                    amount_cents=t.get("amount_cents", 0),
                    description=t.get("description", ""),
                    patron_count=t.get("patron_count", 0),
                    published=t.get("published", True),
                )
                for t in tiers_data
            ]
            
            # Sort by amount
            tiers.sort(key=lambda x: x.amount_cents)
            
            return PatreonGetTiersOutput(
                success=True,
                campaign_id=campaign_id,
                tiers=tiers,
                count=len(tiers),
            )
            
    except PatreonError as e:
        logger.error(f"Patreon error getting tiers: {e}")
        return PatreonGetTiersOutput(
            success=False,
            campaign_id=campaign_id,
            error=e.message,
        )
    except Exception as e:
        logger.error(f"Failed to get tiers: {e}")
        return PatreonGetTiersOutput(
            success=False,
            campaign_id=campaign_id,
            error=str(e),
        )


async def patreon_get_patrons(
    params: PatreonGetPatronsInput
) -> PatreonGetPatronsOutput:
    """Get patrons for a campaign.
    
    Args:
        params.campaign_id: Campaign ID (uses default from env if not provided)
        params.status_filter: Filter by patron status
        params.tier_filter: Filter by tier name (partial match)
        
    Returns:
        List of patrons with details
    """
    campaign_id = params.campaign_id or get_default_campaign_id()
    
    if not campaign_id:
        return PatreonGetPatronsOutput(
            success=False,
            error="No campaign_id provided and PATREON_CREATOR_CAMPAIGN_ID not set",
        )
    
    logger.info(f"Getting Patreon patrons for campaign: {campaign_id}")
    
    try:
        async with PatreonClient() as client:
            members = await client.get_all_patrons(
                campaign_id,
                status_filter=params.status_filter,
            )
            
            patrons = []
            total_monthly = 0
            
            for m in members:
                # Get primary tier
                tier_id = ""
                tier_name = ""
                if m.get("tiers"):
                    tier_id = m["tiers"][0].get("id", "")
                    tier_name = m["tiers"][0].get("title", "")
                
                # Apply tier filter if specified
                if params.tier_filter:
                    if not tier_name or params.tier_filter.lower() not in tier_name.lower():
                        continue
                
                patron = PatronInfo(
                    id=m.get("id", ""),
                    full_name=m.get("full_name", ""),
                    email=m.get("email", ""),
                    patron_status=m.get("patron_status", ""),
                    lifetime_support_cents=m.get("lifetime_support_cents", 0),
                    currently_entitled_amount_cents=m.get("currently_entitled_amount_cents", 0),
                    last_charge_date=m.get("last_charge_date"),
                    last_charge_status=m.get("last_charge_status"),
                    pledge_start=m.get("pledge_relationship_start"),
                    tier_id=tier_id,
                    tier_name=tier_name,
                )
                patrons.append(patron)
                
                if m.get("patron_status") == "active_patron":
                    total_monthly += m.get("currently_entitled_amount_cents", 0)
            
            return PatreonGetPatronsOutput(
                success=True,
                campaign_id=campaign_id,
                patrons=patrons,
                count=len(patrons),
                total_monthly_cents=total_monthly,
            )
            
    except PatreonError as e:
        logger.error(f"Patreon error getting patrons: {e}")
        return PatreonGetPatronsOutput(
            success=False,
            campaign_id=campaign_id,
            error=e.message,
        )
    except Exception as e:
        logger.error(f"Failed to get patrons: {e}")
        return PatreonGetPatronsOutput(
            success=False,
            campaign_id=campaign_id,
            error=str(e),
        )


async def patreon_get_patron(
    params: PatreonGetPatronInput
) -> PatreonGetPatronOutput:
    """Get details for a specific patron.
    
    Args:
        params.patron_id: The patron/member ID
        
    Returns:
        Patron details
    """
    logger.info(f"Getting Patreon patron: {params.patron_id}")
    
    try:
        async with PatreonClient() as client:
            member = await client.get_patron(params.patron_id)
            
            # Get primary tier
            tier_id = ""
            tier_name = ""
            if member.get("tiers"):
                tier_id = member["tiers"][0].get("id", "")
                tier_name = member["tiers"][0].get("title", "")
            
            patron = PatronInfo(
                id=member.get("id", ""),
                full_name=member.get("full_name", ""),
                email=member.get("email", ""),
                patron_status=member.get("patron_status", ""),
                lifetime_support_cents=member.get("lifetime_support_cents", 0),
                currently_entitled_amount_cents=member.get("currently_entitled_amount_cents", 0),
                last_charge_date=member.get("last_charge_date"),
                last_charge_status=member.get("last_charge_status"),
                pledge_start=member.get("pledge_relationship_start"),
                tier_id=tier_id,
                tier_name=tier_name,
            )
            
            return PatreonGetPatronOutput(
                success=True,
                patron=patron,
            )
            
    except PatreonError as e:
        logger.error(f"Patreon error getting patron: {e}")
        return PatreonGetPatronOutput(
            success=False,
            error=e.message,
        )
    except Exception as e:
        logger.error(f"Failed to get patron: {e}")
        return PatreonGetPatronOutput(
            success=False,
            error=str(e),
        )


async def patreon_export_patrons(
    params: PatreonExportPatronsInput
) -> PatreonExportPatronsOutput:
    """Export patrons data for external use.
    
    Args:
        params.campaign_id: Campaign ID
        params.status_filter: Filter by status
        params.format: Export format (json or csv)
        
    Returns:
        Exported data as string
    """
    campaign_id = params.campaign_id or get_default_campaign_id()
    
    if not campaign_id:
        return PatreonExportPatronsOutput(
            success=False,
            error="No campaign_id provided and PATREON_CREATOR_CAMPAIGN_ID not set",
        )
    
    export_format = params.format.lower()
    if export_format not in ("json", "csv"):
        return PatreonExportPatronsOutput(
            success=False,
            error=f"Invalid format '{params.format}'. Use 'json' or 'csv'.",
        )
    
    logger.info(f"Exporting Patreon patrons for campaign: {campaign_id} as {export_format}")
    
    try:
        async with PatreonClient() as client:
            members = await client.get_all_patrons(
                campaign_id,
                status_filter=params.status_filter,
            )
            
            if export_format == "json":
                import json
                data = json.dumps(members, indent=2, default=str)
            else:
                # CSV export
                output = io.StringIO()
                if members:
                    # Define CSV fields
                    fieldnames = [
                        "id", "full_name", "email", "patron_status",
                        "currently_entitled_amount_cents", "lifetime_support_cents",
                        "last_charge_date", "last_charge_status",
                        "pledge_relationship_start", "tier_name", "tier_amount_cents"
                    ]
                    
                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for m in members:
                        tier_name = ""
                        tier_amount = 0
                        if m.get("tiers"):
                            tier_name = m["tiers"][0].get("title", "")
                            tier_amount = m["tiers"][0].get("amount_cents", 0)
                        
                        writer.writerow({
                            "id": m.get("id", ""),
                            "full_name": m.get("full_name", ""),
                            "email": m.get("email", ""),
                            "patron_status": m.get("patron_status", ""),
                            "currently_entitled_amount_cents": m.get("currently_entitled_amount_cents", 0),
                            "lifetime_support_cents": m.get("lifetime_support_cents", 0),
                            "last_charge_date": m.get("last_charge_date", ""),
                            "last_charge_status": m.get("last_charge_status", ""),
                            "pledge_relationship_start": m.get("pledge_relationship_start", ""),
                            "tier_name": tier_name,
                            "tier_amount_cents": tier_amount,
                        })
                
                data = output.getvalue()
            
            return PatreonExportPatronsOutput(
                success=True,
                format=export_format,
                data=data,
                count=len(members),
            )
            
    except PatreonError as e:
        logger.error(f"Patreon error exporting patrons: {e}")
        return PatreonExportPatronsOutput(
            success=False,
            format=export_format,
            error=e.message,
        )
    except Exception as e:
        logger.error(f"Failed to export patrons: {e}")
        return PatreonExportPatronsOutput(
            success=False,
            format=export_format,
            error=str(e),
        )

