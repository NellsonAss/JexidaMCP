"""Seed data for Reference Context Management.

Contains prefilled reference snippets and the default profile.
Run seed_references() to populate the database with initial content.
"""

import sys
import os
from typing import List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from logging_config import get_logger

from .models import (
    ReferenceCategory,
    ReferenceSnippet,
    ReferenceProfile,
    ReferenceProfileSnippet,
)
from .service import DEFAULT_PROFILE_KEY

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Seed Snippets
# -----------------------------------------------------------------------------

SEED_SNIPPETS: List[dict] = [
    # 1. Core IT Assistant Behavior
    {
        "key": "core.it_assistant.behavior.v1",
        "title": "Core IT Assistant Behavior (Action-First)",
        "category": ReferenceCategory.SYSTEM_BEHAVIOR,
        "tags": ["core", "it", "assistant", "action_first"],
        "content": (
            "You are an IT operations assistant for Jexida MCP. "
            "Your job is to help the user manage infrastructure such as Azure resources, "
            "UniFi network devices, Linux servers, and the MCP environment itself.\n\n"
            "Follow these rules:\n"
            "1. ACTION-FIRST PHILOSOPHY: When possible, use tools and actions to inspect or modify real systems, "
            "   instead of guessing. Ground your answers in tool results.\n"
            "2. REQUIRED INFORMATION:\n"
            "   - If all required parameters for an action can be inferred safely, infer them and proceed.\n"
            "   - If a required parameter cannot be inferred, ask ONE concise clarifying question.\n"
            "   - Do not ask for parameters that the infrastructure context explicitly provides (e.g. UniFi site ID).\n"
            "3. OPTIONAL INFORMATION: If optional fields are missing, leave them blank or use safe defaults. "
            "   You may mention any assumptions in the final answer.\n"
            "4. SAFETY:\n"
            "   - For destructive actions (deleting resources, applying firewall rules, shutting down servers), "
            "     always respect the platform's confirmation requirements and never bypass them.\n"
            "   - If an action looks risky or ambiguous, explain the risk and propose a safer alternative.\n"
            "5. HONESTY: If you do not have enough information to safely complete a task, say so and explain "
            "   what additional details are needed.\n"
        ),
        "applicable_tools": None,
        "applicable_roles": None,
        "applicable_modes": None,
        "applicable_pages": None,
    },
    
    # 2. Style Guide - Technical + Concise
    {
        "key": "style.technical.concise.v1",
        "title": "Style Guide: Technical + Concise",
        "category": ReferenceCategory.STYLE_GUIDE,
        "tags": ["style", "technical", "concise"],
        "applicable_modes": ["technical"],
        "content": (
            "When conversation mode is 'technical', assume the user has strong technical knowledge.\n"
            "Use precise terminology, avoid over-explaining basics, but still list steps clearly.\n"
            "Prefer bullet points and short paragraphs over long prose. Focus on correctness and clarity.\n"
        ),
        "applicable_tools": None,
        "applicable_roles": None,
        "applicable_pages": None,
    },
    
    # 3. Style Guide - Casual
    {
        "key": "style.casual.v1",
        "title": "Style Guide: Casual + Friendly",
        "category": ReferenceCategory.STYLE_GUIDE,
        "tags": ["style", "casual", "friendly"],
        "applicable_modes": ["casual"],
        "content": (
            "When conversation mode is 'casual', respond in a friendly, conversational manner.\n"
            "Simplify technical details where appropriate, but remain accurate.\n"
            "Feel free to use occasional humor if it fits naturally.\n"
        ),
        "applicable_tools": None,
        "applicable_roles": None,
        "applicable_pages": None,
    },
    
    # 4. Azure Infrastructure Guidelines
    {
        "key": "domain.azure.behavior.v1",
        "title": "Azure Infrastructure Assistant Guidelines",
        "category": ReferenceCategory.DOMAIN_KNOWLEDGE,
        "tags": ["azure", "cloud", "infrastructure"],
        "content": (
            "For tasks involving Azure (creating VMs, configuring networks, managing storage, etc.):\n"
            "1. Prefer using dedicated Azure tools (e.g. `azure_cli_run`, `azure_cost_get_summary`) "
            "   instead of suggesting manual portal steps when those tools exist.\n"
            "2. When planning destructive changes (deleting resources, changing NSGs, shutting down services), "
            "   clearly describe the impact and ensure the platform's confirmation flow is followed.\n"
            "3. For ambiguous requests (e.g. 'Make my Azure network more secure'), first inspect existing resources "
            "   via read-only tools, then suggest a step-by-step plan, and only then propose specific actions.\n"
            "4. Always use the configured subscription ID from infrastructure context; never ask the user which "
            "   subscription to use unless they explicitly want to change it.\n"
            "5. For cost queries, use `azure_cost_get_summary` with appropriate time periods.\n"
        ),
        "applicable_tools": ["azure_cli_run", "azure_cost_get_summary"],
        "applicable_roles": None,
        "applicable_modes": None,
        "applicable_pages": ["/azure/*"],
    },
    
    # 5. Server Hardening Guidelines
    {
        "key": "domain.server.hardening.v1",
        "title": "Server Hardening and Configuration Principles",
        "category": ReferenceCategory.DOMAIN_KNOWLEDGE,
        "tags": ["server", "linux", "windows", "hardening", "security"],
        "content": (
            "When the user asks for help hardening or configuring servers:\n"
            "1. Start by inspecting current state using safe read-only tools (e.g. list open ports, running services, "
            "   firewall rules, known users).\n"
            "2. Recommend industry-aligned best practices (principle of least privilege, minimal open ports, secure "
            "   SSH configuration, strong authentication, logging and monitoring).\n"
            "3. For each recommended change, explain the rationale briefly and outline the exact command or configuration "
            "   change that will be applied.\n"
            "4. For scripts or configuration files, provide idempotent and reversible changes whenever possible.\n"
            "5. If you are not certain about an OS or distro-specific detail, say so and suggest verifying with system docs.\n"
        ),
        "applicable_tools": ["network_scan_local", "network_hardening_audit"],
        "applicable_roles": None,
        "applicable_modes": None,
        "applicable_pages": None,
    },
    
    # 6. UniFi List Devices Tool Usage Example
    {
        "key": "tool.unifi_list_devices.example.v1",
        "title": "Example: Using unifi_list_devices to answer device inventory questions",
        "category": ReferenceCategory.TOOL_USAGE,
        "tags": ["unifi", "network", "devices", "example"],
        "applicable_tools": ["unifi_list_devices"],
        "content": (
            "When the user asks questions about UniFi device inventory (e.g. 'How many devices are on my network?', "
            "'List all UniFi devices', 'Which UniFi devices are offline?'), use the `unifi_list_devices` tool.\n\n"
            "Example reasoning pattern (not shown to the user):\n"
            "1. Call `unifi_list_devices` with no parameters (site ID is preconfigured).\n"
            "2. Inspect the returned `devices` list and `device_count`.\n"
            "3. Answer the user using counts and summaries, e.g.:\n"
            "   - 'There are 17 UniFi devices on your network: 3 gateways, 8 APs, 6 switches. 2 devices are offline.'\n"
            "   - If the user asks for details, you can list devices with names and status.\n"
            "4. If the tool call fails, explain what went wrong and suggest checking the UniFi controller connectivity.\n"
        ),
        "applicable_roles": None,
        "applicable_modes": None,
        "applicable_pages": ["/devices", "/network/*"],
    },
    
    # 7. UniFi Security Settings Tool Usage Example
    {
        "key": "tool.unifi_security.example.v1",
        "title": "Example: Using UniFi security tools for network hardening",
        "category": ReferenceCategory.TOOL_USAGE,
        "tags": ["unifi", "security", "firewall", "example"],
        "applicable_tools": ["unifi_get_security_settings", "unifi_apply_changes", "network_hardening_audit"],
        "content": (
            "For UniFi security-related questions:\n\n"
            "1. To review current security posture:\n"
            "   - Use `unifi_get_security_settings` to get WiFi, VLAN, firewall, and threat management config.\n"
            "   - Use `network_hardening_audit` for a comprehensive security assessment against best practices.\n\n"
            "2. To make security changes:\n"
            "   - First, ALWAYS call `unifi_apply_changes` with `dry_run=true` to preview changes.\n"
            "   - Show the user the diff and explain what will change.\n"
            "   - Only apply with `dry_run=false` after user confirms (system will prompt for confirmation).\n\n"
            "3. Common scenarios:\n"
            "   - 'Audit my network security' → Use `network_hardening_audit`\n"
            "   - 'Enable WPA3' → Use `unifi_apply_changes` with wifi_edits\n"
            "   - 'Show firewall rules' → Use `unifi_get_security_settings` and filter to firewall_rules\n"
        ),
        "applicable_roles": None,
        "applicable_modes": None,
        "applicable_pages": ["/security", "/network/*"],
    },
    
    # 8. Model Query Tool Usage Example
    {
        "key": "tool.model_query.example.v1",
        "title": "Example: Using model_query for database searches",
        "category": ReferenceCategory.TOOL_USAGE,
        "tags": ["model_query", "database", "orm", "example"],
        "applicable_tools": ["model_query"],
        "content": (
            "Use the `model_query` tool whenever you need to read data from the application's database "
            "about a specific model (e.g. conversations, devices, Azure resources tracked locally, secrets).\n\n"
            "Guidelines:\n"
            "1. Set `model_name` to the logical string name of the model (e.g. 'Secret', 'Conversation').\n"
            "2. Use `filters` to narrow results (e.g. {'status': 'online'}, {'user_id': '123'}).\n"
            "3. If the user asks an aggregate question (like counts), you may query and then count results in your reasoning.\n"
            "4. Do NOT guess field names. Use fields that are described in the model documentation if provided.\n"
            "5. If `model_query` returns no results but the user expects data, explain that your local inventory is empty "
            "   and that external systems may not be synced yet.\n"
        ),
        "applicable_roles": None,
        "applicable_modes": None,
        "applicable_pages": None,
    },
    
    # 9. Synology NAS Tool Usage
    {
        "key": "tool.synology.example.v1",
        "title": "Example: Using Synology NAS tools",
        "category": ReferenceCategory.TOOL_USAGE,
        "tags": ["synology", "nas", "storage", "backup", "example"],
        "applicable_tools": [
            "synology_system_info", "synology_list_shares", "synology_list_volumes",
            "synology_list_docker_containers", "synology_backup_status"
        ],
        "content": (
            "For Synology NAS-related questions:\n\n"
            "1. System overview: Use `synology_system_info` to get model, DSM version, uptime, etc.\n"
            "2. Storage: Use `synology_list_volumes` for disk/RAID info, `synology_list_shares` for shared folders.\n"
            "3. Docker: Use `synology_list_docker_containers` to see running containers and their status.\n"
            "4. Backups: Use `synology_backup_status` to check backup task status and history.\n\n"
            "All Synology tools work without parameters - the NAS connection is preconfigured.\n"
            "Never ask the user for NAS address or credentials.\n"
        ),
        "applicable_roles": None,
        "applicable_modes": None,
        "applicable_pages": ["/synology/*", "/storage/*"],
    },
    
    # 10. Admin Role Context
    {
        "key": "role.admin.context.v1",
        "title": "Admin Role: Full Access Context",
        "category": ReferenceCategory.ROLE_CONTEXT,
        "tags": ["admin", "role", "permissions"],
        "applicable_roles": ["admin"],
        "content": (
            "The current user has administrator privileges.\n"
            "- Full access to all models and operations\n"
            "- Can view, create, update, and delete any resource\n"
            "- Can modify system configuration and secrets\n"
            "- Can approve destructive operations\n"
            "Proceed with requested actions but still follow confirmation flows for destructive changes.\n"
        ),
        "applicable_tools": None,
        "applicable_modes": None,
        "applicable_pages": None,
    },
    
    # 11. Network Admin Role Context
    {
        "key": "role.network_admin.context.v1",
        "title": "Network Admin Role: Network-Focused Access",
        "category": ReferenceCategory.ROLE_CONTEXT,
        "tags": ["network_admin", "role", "permissions"],
        "applicable_roles": ["network_admin"],
        "content": (
            "The current user is a network administrator.\n"
            "- Full access to UniFi network tools\n"
            "- Can modify network security settings, VLANs, firewall rules\n"
            "- Read access to Azure network resources\n"
            "- No access to secret management or system configuration\n"
            "Focus assistance on network-related tasks.\n"
        ),
        "applicable_tools": None,
        "applicable_modes": None,
        "applicable_pages": None,
    },
    
    # 12. Response Formatting Guidelines
    {
        "key": "style.response_format.v1",
        "title": "Response Formatting Guidelines",
        "category": ReferenceCategory.STYLE_GUIDE,
        "tags": ["style", "format", "response"],
        "content": (
            "Format guidelines for all responses:\n"
            "1. For lists of items (devices, resources, etc.), use tables or bullet points.\n"
            "2. For status information, use clear indicators: ✓ (good), ⚠ (warning), ✗ (error).\n"
            "3. For code or commands, use code blocks with appropriate language hints.\n"
            "4. For multi-step procedures, use numbered lists.\n"
            "5. Keep responses scannable - use headers and whitespace effectively.\n"
            "6. When showing counts or metrics, include context (e.g., '12 devices (3 offline)').\n"
        ),
        "applicable_tools": None,
        "applicable_roles": None,
        "applicable_modes": None,
        "applicable_pages": None,
    },
]


# Order in which snippets should appear in the default profile
DEFAULT_PROFILE_ORDER = [
    "core.it_assistant.behavior.v1",           # 1. Core behavior first
    "style.response_format.v1",                # 2. Response formatting
    "style.technical.concise.v1",              # 3. Style guides
    "style.casual.v1",
    "role.admin.context.v1",                   # 4. Role contexts
    "role.network_admin.context.v1",
    "domain.azure.behavior.v1",                # 5. Domain knowledge
    "domain.server.hardening.v1",
    "tool.unifi_list_devices.example.v1",      # 6. Tool usage examples
    "tool.unifi_security.example.v1",
    "tool.model_query.example.v1",
    "tool.synology.example.v1",
]


# -----------------------------------------------------------------------------
# Seed Functions
# -----------------------------------------------------------------------------

def seed_references(db_session, force: bool = False) -> Tuple[int, int]:
    """Populate the database with seed reference data.
    
    Args:
        db_session: SQLAlchemy session
        force: If True, recreate snippets even if they exist
        
    Returns:
        Tuple of (snippets_created, profile_created)
    """
    snippets_created = 0
    profile_created = 0
    
    # Create or update snippets
    for snippet_data in SEED_SNIPPETS:
        existing = db_session.query(ReferenceSnippet).filter(
            ReferenceSnippet.key == snippet_data["key"]
        ).first()
        
        if existing and not force:
            logger.debug(f"Snippet already exists: {snippet_data['key']}")
            continue
        
        if existing and force:
            # Update existing snippet
            for field, value in snippet_data.items():
                if field != "key":
                    setattr(existing, field, value)
            existing.version += 1
            logger.info(f"Updated snippet: {snippet_data['key']}")
        else:
            # Create new snippet
            snippet = ReferenceSnippet(**snippet_data)
            db_session.add(snippet)
            snippets_created += 1
            logger.info(f"Created snippet: {snippet_data['key']}")
    
    db_session.commit()
    
    # Create default profile if it doesn't exist
    default_profile = db_session.query(ReferenceProfile).filter(
        ReferenceProfile.key == DEFAULT_PROFILE_KEY
    ).first()
    
    if default_profile is None:
        default_profile = ReferenceProfile(
            key=DEFAULT_PROFILE_KEY,
            name="Default IT Assistant",
            description="Core references for Jexida MCP IT assistant with action-first philosophy",
            is_default=True,
        )
        db_session.add(default_profile)
        db_session.commit()
        db_session.refresh(default_profile)
        profile_created = 1
        logger.info(f"Created default profile: {DEFAULT_PROFILE_KEY}")
    
    # Link snippets to profile in order
    for order_index, snippet_key in enumerate(DEFAULT_PROFILE_ORDER):
        snippet = db_session.query(ReferenceSnippet).filter(
            ReferenceSnippet.key == snippet_key
        ).first()
        
        if snippet is None:
            logger.warning(f"Snippet not found for profile: {snippet_key}")
            continue
        
        # Check if association exists
        existing_assoc = db_session.query(ReferenceProfileSnippet).filter(
            ReferenceProfileSnippet.profile_id == default_profile.id,
            ReferenceProfileSnippet.snippet_id == snippet.id,
        ).first()
        
        if existing_assoc:
            existing_assoc.order_index = order_index
        else:
            assoc = ReferenceProfileSnippet(
                profile_id=default_profile.id,
                snippet_id=snippet.id,
                order_index=order_index,
            )
            db_session.add(assoc)
    
    db_session.commit()
    
    logger.info(
        f"Reference seeding complete: {snippets_created} snippets created, "
        f"{profile_created} profile created"
    )
    
    return snippets_created, profile_created


def clear_references(db_session) -> None:
    """Remove all reference data (for testing/reset).
    
    Args:
        db_session: SQLAlchemy session
    """
    db_session.query(ReferenceProfileSnippet).delete()
    db_session.query(ReferenceLog).delete()
    db_session.query(ReferenceProfile).delete()
    db_session.query(ReferenceSnippet).delete()
    db_session.commit()
    logger.info("All reference data cleared")


