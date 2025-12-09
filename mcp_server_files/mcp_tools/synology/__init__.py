"""Synology NAS management tools package.

Contains MCP tools for managing Synology NAS devices:
- FileStation: File and folder operations
- Download Station: Download task management
- System: System information and monitoring
- Users: User account management
- Groups: User group management
- Packages: DSM package management
- Surveillance Station: Camera management
- Backup: Hyper Backup task management
- Web Station: Web hosting management
- Shared Folders: Shared folder management
- Network: Network configuration
- Security: Security settings and firewall
- Tasks: Task Scheduler management
- Docker: Container management
- Virtualization: Virtual Machine Manager
- Monitoring: Logs and resource monitoring
"""

# Import tools to trigger registration
from . import filestation
from . import download_station
from . import system
from . import users
from . import groups
from . import packages
from . import surveillance
from . import backup
from . import webstation
from . import shared_folders
from . import network
from . import security
from . import tasks
from . import docker
from . import virtualization
from . import monitoring

# Import client for external use
from .client import (
    SynologyClient,
    SynologyAuthError,
    SynologyConnectionError,
    SynologyAPIError,
    SynologySystemInfo,
    SynologyFileInfo,
    SynologyDownloadTask,
    SynologyStorageVolume,
    SynologyUser,
    SynologyPackage,
    SynologyCamera,
    SynologyBackupTask,
)

__all__ = [
    # Tool modules
    "filestation",
    "download_station",
    "system",
    "users",
    "groups",
    "packages",
    "surveillance",
    "backup",
    "webstation",
    "shared_folders",
    "network",
    "security",
    "tasks",
    "docker",
    "virtualization",
    "monitoring",
    # Client classes
    "SynologyClient",
    "SynologyAuthError",
    "SynologyConnectionError",
    "SynologyAPIError",
    "SynologySystemInfo",
    "SynologyFileInfo",
    "SynologyDownloadTask",
    "SynologyStorageVolume",
    "SynologyUser",
    "SynologyPackage",
    "SynologyCamera",
    "SynologyBackupTask",
]

