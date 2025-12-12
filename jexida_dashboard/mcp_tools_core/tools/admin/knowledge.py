"""Knowledge management tools for MCP platform.

Provides tools for LLMs to read and store knowledge/facts in the MCP system:
- get_mcp_knowledge: Retrieve stored knowledge by key or list all
- store_mcp_knowledge: Store new knowledge for future reference
"""

import logging
from typing import Optional, Dict, Any, List

from asgiref.sync import sync_to_async
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Get Knowledge Tool
# =============================================================================

class GetMCPKnowledgeInput(BaseModel):
    """Input schema for get_mcp_knowledge."""
    
    key: Optional[str] = Field(
        default=None,
        description="Specific knowledge key to retrieve (e.g., 'mcp.deployment.process'). If not provided, lists all knowledge."
    )
    source: Optional[str] = Field(
        default=None,
        description="Filter by source (e.g., 'deployment_learning', 'user_input')"
    )
    search: Optional[str] = Field(
        default=None,
        description="Search term to filter knowledge keys"
    )


class KnowledgeItem(BaseModel):
    """Single knowledge item."""
    key: str
    value: Any
    source: str
    updated_at: str


class GetMCPKnowledgeOutput(BaseModel):
    """Output schema for get_mcp_knowledge."""
    
    success: bool = Field(description="Whether the query succeeded")
    knowledge: List[KnowledgeItem] = Field(default_factory=list, description="List of knowledge items")
    count: int = Field(default=0, description="Number of items returned")
    error: str = Field(default="", description="Error message if failed")


async def get_mcp_knowledge(params: GetMCPKnowledgeInput) -> GetMCPKnowledgeOutput:
    """Retrieve knowledge from the MCP knowledge store.
    
    Use this tool to:
    - Look up specific knowledge by key
    - List all stored knowledge
    - Search for relevant knowledge
    
    Common knowledge keys:
    - mcp.deployment.process: How to deploy new MCP tools
    - mcp.best_practices.*: Best practices for various operations
    
    Args:
        params: Query parameters
        
    Returns:
        Knowledge items matching the query
    """
    logger.info(f"Getting MCP knowledge: key={params.key}, source={params.source}, search={params.search}")
    
    try:
        from mcp_tools_core.models import Fact
        
        @sync_to_async
        def query_facts():
            queryset = Fact.objects.all()
            
            if params.key:
                queryset = queryset.filter(key=params.key)
            
            if params.source:
                queryset = queryset.filter(source=params.source)
            
            if params.search:
                queryset = queryset.filter(key__icontains=params.search)
            
            queryset = queryset.order_by("-updated_at")
            
            return [
                KnowledgeItem(
                    key=f.key,
                    value=f.value,
                    source=f.source or "unknown",
                    updated_at=f.updated_at.isoformat()
                )
                for f in queryset[:50]
            ]
        
        knowledge = await query_facts()
        
        return GetMCPKnowledgeOutput(
            success=True,
            knowledge=knowledge,
            count=len(knowledge)
        )
        
    except Exception as e:
        logger.error(f"Failed to get knowledge: {e}")
        return GetMCPKnowledgeOutput(
            success=False,
            error=str(e)
        )


# =============================================================================
# Store Knowledge Tool
# =============================================================================

class StoreMCPKnowledgeInput(BaseModel):
    """Input schema for store_mcp_knowledge."""
    
    key: str = Field(
        description="Unique key for this knowledge (e.g., 'mcp.deployment.process', 'network.unifi.best_practices')"
    )
    value: Any = Field(
        description="The knowledge to store (can be string, dict, list, etc.)"
    )
    source: str = Field(
        default="llm_learning",
        description="Source of this knowledge (e.g., 'llm_learning', 'user_input', 'tool_discovery')"
    )


class StoreMCPKnowledgeOutput(BaseModel):
    """Output schema for store_mcp_knowledge."""
    
    success: bool = Field(description="Whether the storage succeeded")
    key: str = Field(default="", description="Key of the stored knowledge")
    created: bool = Field(default=False, description="True if new, False if updated existing")
    message: str = Field(default="", description="Status message")
    error: str = Field(default="", description="Error message if failed")


# =============================================================================
# Append Timeseries Tool
# =============================================================================

class AppendMCPTimeseriesInput(BaseModel):
    """Input schema for append_mcp_timeseries."""
    
    key: str = Field(
        description="Timeseries key (e.g., 'unifi.network.history', 'synology.storage.history')"
    )
    data: Dict[str, Any] = Field(
        description="Data point to append (timestamp will be added automatically)"
    )
    max_entries: int = Field(
        default=100,
        description="Maximum entries to keep (oldest removed when exceeded)"
    )
    source: str = Field(
        default="timeseries",
        description="Source identifier for this timeseries"
    )


class AppendMCPTimeseriesOutput(BaseModel):
    """Output schema for append_mcp_timeseries."""
    
    success: bool = Field(description="Whether the append succeeded")
    key: str = Field(default="", description="Timeseries key")
    entry_count: int = Field(default=0, description="Total entries after append")
    message: str = Field(default="", description="Status message")
    error: str = Field(default="", description="Error message if failed")


async def store_mcp_knowledge(params: StoreMCPKnowledgeInput) -> StoreMCPKnowledgeOutput:
    """Store knowledge in the MCP knowledge store for future reference.
    
    Use this tool to:
    - Save learned information for future sessions
    - Record best practices discovered during operations
    - Store configuration details or process documentation
    
    Best practices for keys:
    - Use dot notation for hierarchy: 'category.subcategory.topic'
    - Common prefixes:
      - mcp.*: MCP platform knowledge
      - network.*: Network-related knowledge
      - synology.*: Synology NAS knowledge
      - unifi.*: UniFi network knowledge
      - user.*: User preferences and settings
    
    Args:
        params: Knowledge to store
        
    Returns:
        Storage result
    """
    logger.info(f"Storing MCP knowledge: key={params.key}, source={params.source}")
    
    try:
        from mcp_tools_core.models import Fact
        
        # Validate key format
        if not params.key or len(params.key) < 3:
            return StoreMCPKnowledgeOutput(
                success=False,
                error="Key must be at least 3 characters"
            )
        
        @sync_to_async
        def store_fact():
            fact, created = Fact.objects.update_or_create(
                key=params.key,
                defaults={
                    "value": params.value,
                    "source": params.source,
                }
            )
            return created
        
        created = await store_fact()
        action = "created" if created else "updated"
        logger.info(f"Knowledge {action}: {params.key}")
        
        return StoreMCPKnowledgeOutput(
            success=True,
            key=params.key,
            created=created,
            message=f"Knowledge '{params.key}' {action} successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to store knowledge: {e}")
        return StoreMCPKnowledgeOutput(
            success=False,
            error=str(e)
        )


async def append_mcp_timeseries(params: AppendMCPTimeseriesInput) -> AppendMCPTimeseriesOutput:
    """Append a data point to a timeseries in the MCP knowledge store.
    
    Use this tool for tracking changes over time:
    - Network device counts (WiFi clients, etc.)
    - Storage usage snapshots
    - Performance metrics
    - Any data that changes and needs historical tracking
    
    The tool automatically:
    - Adds ISO timestamp to each entry
    - Maintains max_entries limit (removes oldest when exceeded)
    - Creates the timeseries if it doesn't exist
    
    Args:
        params: Timeseries key and data point to append
        
    Returns:
        Append result with entry count
    """
    from datetime import datetime, timezone
    
    logger.info(f"Appending to timeseries: key={params.key}")
    
    try:
        from mcp_tools_core.models import Fact
        
        # Validate key format
        if not params.key or len(params.key) < 3:
            return AppendMCPTimeseriesOutput(
                success=False,
                error="Key must be at least 3 characters"
            )
        
        @sync_to_async
        def append_to_timeseries():
            # Get existing timeseries or create new
            try:
                fact = Fact.objects.get(key=params.key)
                entries = fact.value if isinstance(fact.value, list) else []
            except Fact.DoesNotExist:
                entries = []
            
            # Create new entry with timestamp
            new_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **params.data
            }
            
            # Append new entry
            entries.append(new_entry)
            
            # Trim to max_entries (keep most recent)
            if len(entries) > params.max_entries:
                entries = entries[-params.max_entries:]
            
            # Save
            fact, created = Fact.objects.update_or_create(
                key=params.key,
                defaults={
                    "value": entries,
                    "source": params.source,
                }
            )
            
            return len(entries), created
        
        entry_count, created = await append_to_timeseries()
        
        action = "created new timeseries" if created else "appended to"
        logger.info(f"Timeseries {action}: {params.key} ({entry_count} entries)")
        
        return AppendMCPTimeseriesOutput(
            success=True,
            key=params.key,
            entry_count=entry_count,
            message=f"Data point added to '{params.key}' ({entry_count} total entries)"
        )
        
    except Exception as e:
        logger.error(f"Failed to append timeseries: {e}")
        return AppendMCPTimeseriesOutput(
            success=False,
            error=str(e)
        )

