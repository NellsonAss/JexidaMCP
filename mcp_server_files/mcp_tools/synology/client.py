"""Synology DSM API client.

Handles authentication and API interactions with Synology NAS devices.
Uses session-based authentication with RSA password encryption.
"""

import asyncio
import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from config import get_settings
from logging_config import get_logger

logger = get_logger(__name__)


class SynologyAuthError(Exception):
    """Authentication failed with the Synology NAS."""
    pass


class SynologyConnectionError(Exception):
    """Failed to connect to the Synology NAS."""
    pass


class SynologyAPIError(Exception):
    """API request to Synology NAS failed."""
    
    def __init__(self, message: str, error_code: Optional[int] = None):
        super().__init__(message)
        self.error_code = error_code


# Common Synology API error codes
SYNOLOGY_ERROR_CODES = {
    100: "Unknown error",
    101: "No parameter of API, method or version",
    102: "The requested API does not exist",
    103: "The requested method does not exist",
    104: "The requested version does not support this functionality",
    105: "The logged in session does not have permission",
    106: "Session timeout",
    107: "Session interrupted by duplicate login",
    400: "Invalid parameter",
    401: "Unknown error of file operation",
    402: "System is too busy",
    403: "Invalid user does this file operation",
    404: "Invalid group does this file operation",
    405: "Invalid user and group does this file operation",
    406: "Can't get user/group information from the account server",
    407: "Operation not permitted",
    408: "No such file or directory",
    409: "Non-supported file system",
    410: "Failed to connect internet-based file system",
    411: "Read-only file system",
    412: "Filename too long in the non-encrypted file system",
    413: "Filename too long in the encrypted file system",
    414: "File already exists",
    415: "Disk quota exceeded",
    416: "No space left on device",
    417: "Input/output error",
    418: "Illegal name or path",
    419: "Illegal file name",
    420: "Illegal file name on FAT file system",
    421: "Device or resource busy",
    599: "No such task of the file operation",
}


@dataclass
class SynologySystemInfo:
    """Synology NAS system information."""
    model: str
    serial: str
    firmware_version: str
    uptime_seconds: int
    cpu_usage_percent: float
    memory_usage_percent: float
    memory_total_mb: int
    memory_used_mb: int
    temperature: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model": self.model,
            "serial": self.serial,
            "firmware_version": self.firmware_version,
            "uptime_seconds": self.uptime_seconds,
            "cpu_usage_percent": self.cpu_usage_percent,
            "memory_usage_percent": self.memory_usage_percent,
            "memory_total_mb": self.memory_total_mb,
            "memory_used_mb": self.memory_used_mb,
            "temperature": self.temperature,
        }


@dataclass
class SynologyFileInfo:
    """File or folder information."""
    name: str
    path: str
    is_dir: bool
    size: int
    create_time: int
    modify_time: int
    access_time: int
    owner: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "path": self.path,
            "is_dir": self.is_dir,
            "size": self.size,
            "create_time": self.create_time,
            "modify_time": self.modify_time,
            "access_time": self.access_time,
            "owner": self.owner,
        }


@dataclass  
class SynologyDownloadTask:
    """Download task information."""
    id: str
    title: str
    status: str  # waiting, downloading, paused, finished, error
    size: int
    size_downloaded: int
    speed_download: int
    percent_done: float
    destination: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "size": self.size,
            "size_downloaded": self.size_downloaded,
            "speed_download": self.speed_download,
            "percent_done": self.percent_done,
            "destination": self.destination,
        }


@dataclass
class SynologyStorageVolume:
    """Storage volume information."""
    id: str
    status: str
    total_size: int
    used_size: int
    free_size: int
    usage_percent: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "status": self.status,
            "total_size": self.total_size,
            "used_size": self.used_size,
            "free_size": self.free_size,
            "usage_percent": self.usage_percent,
        }


@dataclass
class SynologyUser:
    """User account information."""
    name: str
    uid: int
    description: str
    email: str
    expired: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "uid": self.uid,
            "description": self.description,
            "email": self.email,
            "expired": self.expired,
        }


@dataclass
class SynologyPackage:
    """DSM package information."""
    id: str
    name: str
    version: str
    status: str  # running, stopped
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "status": self.status,
            "description": self.description,
        }


@dataclass
class SynologyCamera:
    """Surveillance Station camera information."""
    id: int
    name: str
    enabled: bool
    status: str
    ip_address: str
    model: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "status": self.status,
            "ip_address": self.ip_address,
            "model": self.model,
        }


@dataclass
class SynologyBackupTask:
    """Hyper Backup task information."""
    task_id: int
    name: str
    status: str
    last_run_time: int
    next_run_time: int
    target_type: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status,
            "last_run_time": self.last_run_time,
            "next_run_time": self.next_run_time,
            "target_type": self.target_type,
        }


class SynologyClient:
    """Async client for Synology DSM API.
    
    Supports DSM 6.x and 7.x API patterns.
    Uses session-based cookie authentication.
    
    Usage:
        async with SynologyClient() as client:
            info = await client.get_system_info()
    """
    
    # API endpoint mappings
    API_INFO = {
        "SYNO.API.Info": {"path": "query.cgi", "version": 1},
        "SYNO.API.Auth": {"path": "auth.cgi", "version": 6},
        "SYNO.API.Encryption": {"path": "encryption.cgi", "version": 1},
        "SYNO.FileStation.List": {"path": "entry.cgi", "version": 2},
        "SYNO.FileStation.Info": {"path": "entry.cgi", "version": 2},
        "SYNO.FileStation.Search": {"path": "entry.cgi", "version": 2},
        "SYNO.FileStation.CreateFolder": {"path": "entry.cgi", "version": 2},
        "SYNO.FileStation.Rename": {"path": "entry.cgi", "version": 2},
        "SYNO.FileStation.Delete": {"path": "entry.cgi", "version": 2},
        "SYNO.FileStation.Upload": {"path": "entry.cgi", "version": 2},
        "SYNO.FileStation.Download": {"path": "entry.cgi", "version": 2},
        "SYNO.FileStation.CopyMove": {"path": "entry.cgi", "version": 3},
        "SYNO.DownloadStation.Task": {"path": "DownloadStation/task.cgi", "version": 1},
        "SYNO.DownloadStation.Info": {"path": "DownloadStation/info.cgi", "version": 1},
        "SYNO.Core.System": {"path": "entry.cgi", "version": 3},
        "SYNO.Core.System.Utilization": {"path": "entry.cgi", "version": 1},
        "SYNO.Storage.CGI.Storage": {"path": "entry.cgi", "version": 1},
        "SYNO.Core.User": {"path": "entry.cgi", "version": 1},
        "SYNO.Core.Package": {"path": "entry.cgi", "version": 1},
        "SYNO.SurveillanceStation.Camera": {"path": "entry.cgi", "version": 9},
        "SYNO.SurveillanceStation.Info": {"path": "entry.cgi", "version": 5},
        "SYNO.Backup.Task": {"path": "entry.cgi", "version": 1},
    }
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        verify_ssl: Optional[bool] = None,
        timeout: Optional[int] = None,
        otp_code: Optional[str] = None,
    ):
        """Initialize Synology client.
        
        Args:
            base_url: NAS URL (defaults to config)
            username: Admin username (defaults to config)
            password: Admin password (defaults to config)
            verify_ssl: Verify SSL certs (defaults to config)
            timeout: Request timeout in seconds (defaults to config)
            otp_code: Optional OTP code for 2FA
        """
        settings = get_settings()
        
        self.base_url = (base_url or settings.synology_url or "").rstrip("/")
        self.username = username or settings.synology_username
        self.password = password or settings.synology_password
        self.verify_ssl = verify_ssl if verify_ssl is not None else settings.synology_verify_ssl
        self.timeout = timeout or settings.synology_timeout
        self.otp_code = otp_code
        
        self._client: Optional[httpx.AsyncClient] = None
        self._sid: Optional[str] = None
        self._api_info: Dict[str, Dict[str, Any]] = {}
        
    async def __aenter__(self) -> "SynologyClient":
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
    
    async def connect(self) -> None:
        """Establish connection and authenticate."""
        if not self.base_url:
            raise SynologyConnectionError("Synology NAS URL not configured")
        if not self.username or not self.password:
            raise SynologyAuthError("Synology credentials not configured")
        
        # Create HTTP client
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            verify=self.verify_ssl,
            timeout=self.timeout,
            follow_redirects=True,
        )
        
        try:
            # Get API info
            await self._get_api_info()
            
            # Authenticate
            await self._authenticate()
            
            logger.info(f"Connected to Synology NAS at {self.base_url}")
            
        except httpx.ConnectError as e:
            await self.disconnect()
            raise SynologyConnectionError(f"Failed to connect to {self.base_url}: {e}")
        except httpx.TimeoutException as e:
            await self.disconnect()
            raise SynologyConnectionError(f"Connection timeout to {self.base_url}: {e}")
    
    async def disconnect(self) -> None:
        """Close connection and logout."""
        if self._sid and self._client:
            try:
                await self._api_request(
                    "SYNO.API.Auth",
                    "logout",
                    session="FileStation",
                )
            except Exception:
                pass  # Ignore logout errors
        
        if self._client:
            await self._client.aclose()
            self._client = None
        
        self._sid = None
    
    async def _get_api_info(self) -> None:
        """Query available APIs from the NAS."""
        response = await self._client.get(
            "/webapi/query.cgi",
            params={
                "api": "SYNO.API.Info",
                "version": 1,
                "method": "query",
                "query": "all",
            }
        )
        
        data = response.json()
        if data.get("success"):
            self._api_info = data.get("data", {})
        else:
            logger.warning("Failed to get API info, using defaults")
    
    async def _authenticate(self) -> None:
        """Authenticate with the NAS."""
        params = {
            "account": self.username,
            "passwd": self.password,
            "session": "FileStation",
            "format": "sid",
        }
        
        if self.otp_code:
            params["otp_code"] = self.otp_code
        
        response = await self._client.get(
            "/webapi/auth.cgi",
            params={
                "api": "SYNO.API.Auth",
                "version": 6,
                "method": "login",
                **params,
            }
        )
        
        data = response.json()
        
        if not data.get("success"):
            error_code = data.get("error", {}).get("code", 0)
            error_msg = self._get_error_message(error_code)
            raise SynologyAuthError(f"Authentication failed: {error_msg} (code: {error_code})")
        
        self._sid = data.get("data", {}).get("sid")
        if not self._sid:
            raise SynologyAuthError("No session ID received")
        
        logger.debug(f"Authenticated with session ID: {self._sid[:8]}...")
    
    def _get_error_message(self, code: int) -> str:
        """Get human-readable error message for error code."""
        return SYNOLOGY_ERROR_CODES.get(code, f"Unknown error code {code}")
    
    async def _api_request(
        self,
        api: str,
        method: str,
        version: Optional[int] = None,
        **params
    ) -> Dict[str, Any]:
        """Make an API request.
        
        Args:
            api: API name (e.g., "SYNO.FileStation.List")
            method: Method name (e.g., "list")
            version: API version (uses default if not specified)
            **params: Additional parameters
            
        Returns:
            API response data
            
        Raises:
            SynologyAPIError: If request fails
        """
        if not self._client:
            raise SynologyAPIError("Not connected")
        
        # Get API path and version
        api_info = self._api_info.get(api) or self.API_INFO.get(api)
        if not api_info:
            raise SynologyAPIError(f"Unknown API: {api}")
        
        path = api_info.get("path", "entry.cgi")
        ver = version or api_info.get("version", 1)
        
        # Build request parameters
        request_params = {
            "api": api,
            "version": ver,
            "method": method,
            **params,
        }
        
        # Add session ID if authenticated
        if self._sid:
            request_params["_sid"] = self._sid
        
        # Make request
        try:
            response = await self._client.get(
                f"/webapi/{path}",
                params=request_params,
            )
            data = response.json()
        except httpx.TimeoutException:
            raise SynologyAPIError(f"Request timeout for {api}.{method}")
        except Exception as e:
            raise SynologyAPIError(f"Request failed for {api}.{method}: {e}")
        
        # Check for errors
        if not data.get("success"):
            error = data.get("error", {})
            error_code = error.get("code", 0)
            error_msg = self._get_error_message(error_code)
            raise SynologyAPIError(f"{api}.{method} failed: {error_msg}", error_code)
        
        return data.get("data", {})
    
    async def _api_post(
        self,
        api: str,
        method: str,
        version: Optional[int] = None,
        files: Optional[Dict[str, Any]] = None,
        **params
    ) -> Dict[str, Any]:
        """Make a POST API request (for uploads).
        
        Args:
            api: API name
            method: Method name
            version: API version
            files: Files to upload
            **params: Additional parameters
            
        Returns:
            API response data
        """
        if not self._client:
            raise SynologyAPIError("Not connected")
        
        api_info = self._api_info.get(api) or self.API_INFO.get(api)
        if not api_info:
            raise SynologyAPIError(f"Unknown API: {api}")
        
        path = api_info.get("path", "entry.cgi")
        ver = version or api_info.get("version", 1)
        
        # Build form data
        form_data = {
            "api": api,
            "version": str(ver),
            "method": method,
            **{k: str(v) for k, v in params.items()},
        }
        
        if self._sid:
            form_data["_sid"] = self._sid
        
        try:
            response = await self._client.post(
                f"/webapi/{path}",
                data=form_data,
                files=files,
            )
            data = response.json()
        except Exception as e:
            raise SynologyAPIError(f"POST request failed for {api}.{method}: {e}")
        
        if not data.get("success"):
            error = data.get("error", {})
            error_code = error.get("code", 0)
            error_msg = self._get_error_message(error_code)
            raise SynologyAPIError(f"{api}.{method} failed: {error_msg}", error_code)
        
        return data.get("data", {})
    
    # -------------------------------------------------------------------------
    # System Information
    # -------------------------------------------------------------------------
    
    async def get_system_info(self) -> SynologySystemInfo:
        """Get system information."""
        # Get system info
        system_data = await self._api_request(
            "SYNO.Core.System",
            "info",
        )
        
        # Get utilization data
        util_data = await self._api_request(
            "SYNO.Core.System.Utilization",
            "get",
        )
        
        cpu = util_data.get("cpu", {})
        memory = util_data.get("memory", {})
        
        # Calculate CPU usage
        cpu_user = cpu.get("user_load", 0)
        cpu_system = cpu.get("system_load", 0)
        cpu_usage = cpu_user + cpu_system
        
        # Calculate memory usage
        mem_total = memory.get("memory_size", 0)
        mem_real_usage = memory.get("real_usage", 0)
        mem_used = int(mem_total * mem_real_usage / 100) if mem_total else 0
        
        return SynologySystemInfo(
            model=system_data.get("model", "Unknown"),
            serial=system_data.get("serial", "Unknown"),
            firmware_version=system_data.get("firmware_ver", "Unknown"),
            uptime_seconds=system_data.get("uptime", 0),
            cpu_usage_percent=cpu_usage,
            memory_usage_percent=mem_real_usage,
            memory_total_mb=mem_total // (1024 * 1024) if mem_total else 0,
            memory_used_mb=mem_used // (1024 * 1024) if mem_used else 0,
            temperature=system_data.get("temperature"),
        )
    
    async def get_storage_info(self) -> List[SynologyStorageVolume]:
        """Get storage volume information."""
        data = await self._api_request(
            "SYNO.Storage.CGI.Storage",
            "load_info",
        )
        
        volumes = []
        for vol in data.get("volumes", []):
            total = vol.get("size", {}).get("total", 0)
            used = vol.get("size", {}).get("used", 0)
            
            volumes.append(SynologyStorageVolume(
                id=vol.get("id", ""),
                status=vol.get("status", "unknown"),
                total_size=int(total) if total else 0,
                used_size=int(used) if used else 0,
                free_size=int(total) - int(used) if total and used else 0,
                usage_percent=round(int(used) / int(total) * 100, 2) if total else 0,
            ))
        
        return volumes
    
    async def get_network_info(self) -> Dict[str, Any]:
        """Get network interface information."""
        data = await self._api_request(
            "SYNO.Core.System",
            "info",
        )
        
        return {
            "hostname": data.get("hostname", ""),
            "dns": data.get("dns_name", ""),
        }
    
    # -------------------------------------------------------------------------
    # FileStation
    # -------------------------------------------------------------------------
    
    async def list_files(
        self,
        folder_path: str = "/",
        offset: int = 0,
        limit: int = 1000,
        sort_by: str = "name",
        sort_direction: str = "asc",
    ) -> List[SynologyFileInfo]:
        """List files in a folder.
        
        Args:
            folder_path: Path to list
            offset: Starting offset
            limit: Maximum items to return
            sort_by: Sort field (name, size, mtime)
            sort_direction: Sort direction (asc, desc)
            
        Returns:
            List of file info objects
        """
        data = await self._api_request(
            "SYNO.FileStation.List",
            "list",
            folder_path=folder_path,
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            sort_direction=sort_direction,
            additional='["size","time","owner"]',
        )
        
        files = []
        for item in data.get("files", []):
            additional = item.get("additional", {})
            time_info = additional.get("time", {})
            owner_info = additional.get("owner", {})
            
            files.append(SynologyFileInfo(
                name=item.get("name", ""),
                path=item.get("path", ""),
                is_dir=item.get("isdir", False),
                size=additional.get("size", 0),
                create_time=time_info.get("crtime", 0),
                modify_time=time_info.get("mtime", 0),
                access_time=time_info.get("atime", 0),
                owner=owner_info.get("user", ""),
            ))
        
        return files
    
    async def get_file_info(self, path: str) -> SynologyFileInfo:
        """Get information about a specific file or folder."""
        data = await self._api_request(
            "SYNO.FileStation.List",
            "getinfo",
            path=f'["{path}"]',
            additional='["size","time","owner"]',
        )
        
        files = data.get("files", [])
        if not files:
            raise SynologyAPIError(f"File not found: {path}", 408)
        
        item = files[0]
        additional = item.get("additional", {})
        time_info = additional.get("time", {})
        owner_info = additional.get("owner", {})
        
        return SynologyFileInfo(
            name=item.get("name", ""),
            path=item.get("path", ""),
            is_dir=item.get("isdir", False),
            size=additional.get("size", 0),
            create_time=time_info.get("crtime", 0),
            modify_time=time_info.get("mtime", 0),
            access_time=time_info.get("atime", 0),
            owner=owner_info.get("user", ""),
        )
    
    async def create_folder(self, folder_path: str, name: str) -> SynologyFileInfo:
        """Create a new folder.
        
        Args:
            folder_path: Parent folder path
            name: Name of new folder
            
        Returns:
            Info about created folder
        """
        data = await self._api_request(
            "SYNO.FileStation.CreateFolder",
            "create",
            folder_path=f'["{folder_path}"]',
            name=f'["{name}"]',
        )
        
        folders = data.get("folders", [])
        if folders:
            folder = folders[0]
            return SynologyFileInfo(
                name=folder.get("name", name),
                path=folder.get("path", f"{folder_path}/{name}"),
                is_dir=True,
                size=0,
                create_time=0,
                modify_time=0,
                access_time=0,
                owner="",
            )
        
        # Return basic info if API doesn't return folder data
        return SynologyFileInfo(
            name=name,
            path=f"{folder_path}/{name}",
            is_dir=True,
            size=0,
            create_time=0,
            modify_time=0,
            access_time=0,
            owner="",
        )
    
    async def delete_files(self, paths: List[str]) -> bool:
        """Delete files or folders.
        
        Args:
            paths: List of paths to delete
            
        Returns:
            True if successful
        """
        path_json = json.dumps(paths)
        
        # Start delete task
        data = await self._api_request(
            "SYNO.FileStation.Delete",
            "start",
            path=path_json,
            recursive=True,
        )
        
        task_id = data.get("taskid")
        if not task_id:
            return True  # No task means immediate completion
        
        # Poll for completion
        for _ in range(60):  # Max 60 seconds
            status = await self._api_request(
                "SYNO.FileStation.Delete",
                "status",
                taskid=task_id,
            )
            
            if status.get("finished"):
                return True
            
            await asyncio.sleep(1)
        
        raise SynologyAPIError("Delete operation timed out")
    
    async def move_files(
        self,
        paths: List[str],
        dest_folder: str,
        overwrite: bool = False,
    ) -> bool:
        """Move files to another location.
        
        Args:
            paths: Source paths
            dest_folder: Destination folder
            overwrite: Overwrite existing files
            
        Returns:
            True if successful
        """
        path_json = json.dumps(paths)
        
        data = await self._api_request(
            "SYNO.FileStation.CopyMove",
            "start",
            path=path_json,
            dest_folder_path=dest_folder,
            overwrite=overwrite,
            remove_src=True,
        )
        
        task_id = data.get("taskid")
        if not task_id:
            return True
        
        # Poll for completion
        for _ in range(120):  # Max 2 minutes
            status = await self._api_request(
                "SYNO.FileStation.CopyMove",
                "status",
                taskid=task_id,
            )
            
            if status.get("finished"):
                return True
            
            await asyncio.sleep(1)
        
        raise SynologyAPIError("Move operation timed out")
    
    async def rename_file(self, path: str, new_name: str) -> SynologyFileInfo:
        """Rename a file or folder.
        
        Args:
            path: Path to file/folder
            new_name: New name
            
        Returns:
            Info about renamed file
        """
        data = await self._api_request(
            "SYNO.FileStation.Rename",
            "rename",
            path=f'["{path}"]',
            name=f'["{new_name}"]',
        )
        
        files = data.get("files", [])
        if files:
            item = files[0]
            return SynologyFileInfo(
                name=item.get("name", new_name),
                path=item.get("path", ""),
                is_dir=item.get("isdir", False),
                size=0,
                create_time=0,
                modify_time=0,
                access_time=0,
                owner="",
            )
        
        raise SynologyAPIError("Rename failed - no response data")
    
    async def search_files(
        self,
        folder_path: str,
        pattern: str,
        extension: Optional[str] = None,
        file_type: Optional[str] = None,  # file, dir, all
    ) -> List[SynologyFileInfo]:
        """Search for files.
        
        Args:
            folder_path: Folder to search in
            pattern: Search pattern (supports wildcards)
            extension: File extension filter
            file_type: Type filter (file, dir, all)
            
        Returns:
            List of matching files
        """
        params = {
            "folder_path": f'["{folder_path}"]',
            "pattern": pattern,
            "recursive": True,
        }
        
        if extension:
            params["extension"] = extension
        if file_type and file_type != "all":
            params["filetype"] = file_type
        
        # Start search task
        data = await self._api_request(
            "SYNO.FileStation.Search",
            "start",
            **params,
        )
        
        task_id = data.get("taskid")
        if not task_id:
            raise SynologyAPIError("Search failed to start")
        
        # Poll for results
        files = []
        for _ in range(60):
            status = await self._api_request(
                "SYNO.FileStation.Search",
                "list",
                taskid=task_id,
                offset=0,
                limit=1000,
                additional='["size","time","owner"]',
            )
            
            if status.get("finished"):
                for item in status.get("files", []):
                    additional = item.get("additional", {})
                    time_info = additional.get("time", {})
                    owner_info = additional.get("owner", {})
                    
                    files.append(SynologyFileInfo(
                        name=item.get("name", ""),
                        path=item.get("path", ""),
                        is_dir=item.get("isdir", False),
                        size=additional.get("size", 0),
                        create_time=time_info.get("crtime", 0),
                        modify_time=time_info.get("mtime", 0),
                        access_time=time_info.get("atime", 0),
                        owner=owner_info.get("user", ""),
                    ))
                
                # Stop search task
                await self._api_request(
                    "SYNO.FileStation.Search",
                    "stop",
                    taskid=task_id,
                )
                break
            
            await asyncio.sleep(0.5)
        
        return files
    
    # -------------------------------------------------------------------------
    # Download Station
    # -------------------------------------------------------------------------
    
    async def list_downloads(self) -> List[SynologyDownloadTask]:
        """List all download tasks."""
        data = await self._api_request(
            "SYNO.DownloadStation.Task",
            "list",
            additional="detail,transfer",
        )
        
        tasks = []
        for task in data.get("tasks", []):
            additional = task.get("additional", {})
            detail = additional.get("detail", {})
            transfer = additional.get("transfer", {})
            
            size = task.get("size", 0)
            downloaded = transfer.get("size_downloaded", 0)
            
            tasks.append(SynologyDownloadTask(
                id=task.get("id", ""),
                title=task.get("title", ""),
                status=task.get("status", ""),
                size=size,
                size_downloaded=downloaded,
                speed_download=transfer.get("speed_download", 0),
                percent_done=round(downloaded / size * 100, 2) if size else 0,
                destination=detail.get("destination", ""),
            ))
        
        return tasks
    
    async def add_download(
        self,
        uri: str,
        destination: Optional[str] = None,
    ) -> str:
        """Add a download task.
        
        Args:
            uri: URL or magnet link
            destination: Destination folder
            
        Returns:
            Task ID
        """
        params = {"uri": uri}
        if destination:
            params["destination"] = destination
        
        data = await self._api_request(
            "SYNO.DownloadStation.Task",
            "create",
            **params,
        )
        
        return data.get("id", "")
    
    async def pause_download(self, task_id: str) -> bool:
        """Pause a download task."""
        await self._api_request(
            "SYNO.DownloadStation.Task",
            "pause",
            id=task_id,
        )
        return True
    
    async def resume_download(self, task_id: str) -> bool:
        """Resume a paused download task."""
        await self._api_request(
            "SYNO.DownloadStation.Task",
            "resume",
            id=task_id,
        )
        return True
    
    async def delete_download(self, task_id: str, force_complete: bool = False) -> bool:
        """Delete a download task.
        
        Args:
            task_id: Task ID to delete
            force_complete: Delete even if not complete
            
        Returns:
            True if successful
        """
        await self._api_request(
            "SYNO.DownloadStation.Task",
            "delete",
            id=task_id,
            force_complete=force_complete,
        )
        return True
    
    # -------------------------------------------------------------------------
    # User Management
    # -------------------------------------------------------------------------
    
    async def list_users(self) -> List[SynologyUser]:
        """List all user accounts."""
        data = await self._api_request(
            "SYNO.Core.User",
            "list",
            offset=0,
            limit=1000,
        )
        
        users = []
        for user in data.get("users", []):
            users.append(SynologyUser(
                name=user.get("name", ""),
                uid=user.get("uid", 0),
                description=user.get("description", ""),
                email=user.get("email", ""),
                expired=user.get("expired", "normal") != "normal",
            ))
        
        return users
    
    async def get_user_info(self, username: str) -> SynologyUser:
        """Get information about a specific user."""
        data = await self._api_request(
            "SYNO.Core.User",
            "get",
            name=username,
        )
        
        users = data.get("users", [])
        if not users:
            raise SynologyAPIError(f"User not found: {username}")
        
        user = users[0]
        return SynologyUser(
            name=user.get("name", ""),
            uid=user.get("uid", 0),
            description=user.get("description", ""),
            email=user.get("email", ""),
            expired=user.get("expired", "normal") != "normal",
        )
    
    async def create_user(
        self,
        username: str,
        password: str,
        description: str = "",
        email: str = "",
    ) -> bool:
        """Create a new user account.
        
        Args:
            username: Username
            password: Password
            description: User description
            email: Email address
            
        Returns:
            True if successful
        """
        await self._api_request(
            "SYNO.Core.User",
            "create",
            name=username,
            password=password,
            description=description,
            email=email,
        )
        return True
    
    async def delete_user(self, username: str) -> bool:
        """Delete a user account."""
        await self._api_request(
            "SYNO.Core.User",
            "delete",
            name=f'["{username}"]',
        )
        return True
    
    # -------------------------------------------------------------------------
    # Package Management
    # -------------------------------------------------------------------------
    
    async def list_packages(self, installed_only: bool = True) -> List[SynologyPackage]:
        """List DSM packages.
        
        Args:
            installed_only: Only return installed packages
            
        Returns:
            List of packages
        """
        data = await self._api_request(
            "SYNO.Core.Package",
            "list",
        )
        
        packages = []
        for pkg in data.get("packages", []):
            if installed_only and not pkg.get("installed"):
                continue
            
            packages.append(SynologyPackage(
                id=pkg.get("id", ""),
                name=pkg.get("name", pkg.get("dname", "")),
                version=pkg.get("version", ""),
                status="running" if pkg.get("running") else "stopped",
                description=pkg.get("desc", ""),
            ))
        
        return packages
    
    async def install_package(self, package_name: str) -> bool:
        """Install a DSM package."""
        await self._api_request(
            "SYNO.Core.Package",
            "install",
            name=package_name,
        )
        return True
    
    async def uninstall_package(self, package_name: str) -> bool:
        """Uninstall a DSM package."""
        await self._api_request(
            "SYNO.Core.Package",
            "uninstall",
            name=package_name,
        )
        return True
    
    # -------------------------------------------------------------------------
    # Surveillance Station
    # -------------------------------------------------------------------------
    
    async def list_cameras(self) -> List[SynologyCamera]:
        """List all cameras in Surveillance Station."""
        try:
            data = await self._api_request(
                "SYNO.SurveillanceStation.Camera",
                "List",
                offset=0,
                limit=100,
            )
        except SynologyAPIError as e:
            if e.error_code == 102:  # API doesn't exist
                raise SynologyAPIError("Surveillance Station is not installed")
            raise
        
        cameras = []
        for cam in data.get("cameras", []):
            cameras.append(SynologyCamera(
                id=cam.get("id", 0),
                name=cam.get("name", ""),
                enabled=cam.get("enabled", False),
                status=cam.get("status", "unknown"),
                ip_address=cam.get("ip", ""),
                model=cam.get("model", ""),
            ))
        
        return cameras
    
    async def get_camera_info(self, camera_id: int) -> SynologyCamera:
        """Get information about a specific camera."""
        data = await self._api_request(
            "SYNO.SurveillanceStation.Camera",
            "GetInfo",
            cameraIds=str(camera_id),
        )
        
        cameras = data.get("cameras", [])
        if not cameras:
            raise SynologyAPIError(f"Camera not found: {camera_id}")
        
        cam = cameras[0]
        return SynologyCamera(
            id=cam.get("id", camera_id),
            name=cam.get("name", ""),
            enabled=cam.get("enabled", False),
            status=cam.get("status", "unknown"),
            ip_address=cam.get("ip", ""),
            model=cam.get("model", ""),
        )
    
    async def enable_camera(self, camera_id: int, enabled: bool = True) -> bool:
        """Enable or disable a camera."""
        await self._api_request(
            "SYNO.SurveillanceStation.Camera",
            "Enable" if enabled else "Disable",
            cameraIds=str(camera_id),
        )
        return True
    
    # -------------------------------------------------------------------------
    # Backup (Hyper Backup)
    # -------------------------------------------------------------------------
    
    async def list_backup_tasks(self) -> List[SynologyBackupTask]:
        """List Hyper Backup tasks."""
        try:
            data = await self._api_request(
                "SYNO.Backup.Task",
                "list",
            )
        except SynologyAPIError as e:
            if e.error_code == 102:  # API doesn't exist
                raise SynologyAPIError("Hyper Backup is not installed")
            raise
        
        tasks = []
        for task in data.get("tasks", []):
            tasks.append(SynologyBackupTask(
                task_id=task.get("task_id", 0),
                name=task.get("name", ""),
                status=task.get("status", "unknown"),
                last_run_time=task.get("last_result_time", 0),
                next_run_time=task.get("next_trigger_time", 0),
                target_type=task.get("target_type", ""),
            ))
        
        return tasks
    
    async def run_backup_task(self, task_id: int) -> bool:
        """Trigger a backup task to run."""
        await self._api_request(
            "SYNO.Backup.Task",
            "backup",
            task_id=task_id,
        )
        return True
    
    async def get_backup_status(self, task_id: int) -> Dict[str, Any]:
        """Get the current status of a backup task."""
        data = await self._api_request(
            "SYNO.Backup.Task",
            "status",
            task_id=task_id,
        )
        
        return {
            "task_id": task_id,
            "state": data.get("state", "unknown"),
            "progress": data.get("progress", 0),
            "transferred_bytes": data.get("transferred_bytes", 0),
            "error": data.get("error", None),
        }
    
    # -------------------------------------------------------------------------
    # Shared Folders
    # -------------------------------------------------------------------------
    
    async def list_shared_folders(self) -> List[Dict[str, Any]]:
        """List all shared folders."""
        data = await self._api_request(
            "SYNO.Core.Share",
            "list",
            additional='["encryption","volume_status"]',
        )
        
        folders = []
        for share in data.get("shares", []):
            folders.append({
                "name": share.get("name", ""),
                "path": share.get("path", ""),
                "vol_path": share.get("vol_path", ""),
                "desc": share.get("desc", ""),
                "enable_recycle_bin": share.get("enable_recycle_bin", False),
                "encryption": share.get("encryption", 0),
                "is_aclmode": share.get("is_aclmode", False),
            })
        
        return folders
    
    async def get_shared_folder_info(self, name: str) -> Dict[str, Any]:
        """Get information about a specific shared folder."""
        data = await self._api_request(
            "SYNO.Core.Share",
            "get",
            name=name,
            additional='["encryption","volume_status","share_quota"]',
        )
        
        share = data.get("shares", [{}])[0] if data.get("shares") else {}
        return {
            "name": share.get("name", name),
            "path": share.get("path", ""),
            "vol_path": share.get("vol_path", ""),
            "desc": share.get("desc", ""),
            "enable_recycle_bin": share.get("enable_recycle_bin", False),
            "encryption": share.get("encryption", 0),
            "is_aclmode": share.get("is_aclmode", False),
            "quota_value": share.get("quota_value", 0),
        }
    
    async def create_shared_folder(
        self,
        name: str,
        vol_path: str = "/volume1",
        desc: str = "",
        enable_recycle_bin: bool = True,
    ) -> bool:
        """Create a new shared folder.
        
        Args:
            name: Shared folder name
            vol_path: Volume path (e.g., /volume1)
            desc: Description
            enable_recycle_bin: Enable recycle bin
            
        Returns:
            True if successful
        """
        await self._api_request(
            "SYNO.Core.Share",
            "create",
            name=name,
            vol_path=vol_path,
            desc=desc,
            enable_recycle_bin=enable_recycle_bin,
        )
        return True
    
    async def delete_shared_folder(self, name: str) -> bool:
        """Delete a shared folder."""
        await self._api_request(
            "SYNO.Core.Share",
            "delete",
            name=name,
        )
        return True
    
    # -------------------------------------------------------------------------
    # Groups
    # -------------------------------------------------------------------------
    
    async def list_groups(self) -> List[Dict[str, Any]]:
        """List all user groups."""
        data = await self._api_request(
            "SYNO.Core.Group",
            "list",
            offset=0,
            limit=1000,
        )
        
        groups = []
        for group in data.get("groups", []):
            groups.append({
                "name": group.get("name", ""),
                "gid": group.get("gid", 0),
                "description": group.get("description", ""),
            })
        
        return groups
    
    async def get_group_info(self, name: str) -> Dict[str, Any]:
        """Get information about a specific group."""
        data = await self._api_request(
            "SYNO.Core.Group",
            "get",
            name=name,
        )
        
        group = data.get("groups", [{}])[0] if data.get("groups") else {}
        return {
            "name": group.get("name", name),
            "gid": group.get("gid", 0),
            "description": group.get("description", ""),
            "members": group.get("members", []),
        }
    
    async def create_group(self, name: str, description: str = "") -> bool:
        """Create a new user group."""
        await self._api_request(
            "SYNO.Core.Group",
            "create",
            name=name,
            description=description,
        )
        return True
    
    async def delete_group(self, name: str) -> bool:
        """Delete a user group."""
        await self._api_request(
            "SYNO.Core.Group",
            "delete",
            name=f'["{name}"]',
        )
        return True
    
    async def add_group_member(self, group_name: str, username: str) -> bool:
        """Add a user to a group."""
        await self._api_request(
            "SYNO.Core.Group.Member",
            "add",
            group=group_name,
            member=f'["{username}"]',
        )
        return True
    
    async def remove_group_member(self, group_name: str, username: str) -> bool:
        """Remove a user from a group."""
        await self._api_request(
            "SYNO.Core.Group.Member",
            "remove",
            group=group_name,
            member=f'["{username}"]',
        )
        return True
    
    # -------------------------------------------------------------------------
    # Web Station
    # -------------------------------------------------------------------------
    
    async def list_web_services(self) -> List[Dict[str, Any]]:
        """List all web services/virtual hosts."""
        try:
            data = await self._api_request(
                "SYNO.WebStation.WebService",
                "list",
            )
        except SynologyAPIError as e:
            if e.error_code == 102:
                raise SynologyAPIError("Web Station is not installed")
            raise
        
        services = []
        for svc in data.get("services", []):
            services.append({
                "id": svc.get("id", ""),
                "service_id": svc.get("service_id", ""),
                "fqdn": svc.get("fqdn", ""),
                "root": svc.get("root", ""),
                "backend": svc.get("backend", ""),
                "php": svc.get("php", ""),
                "status": svc.get("status", ""),
                "https": svc.get("https", False),
                "http_port": svc.get("http_port", 80),
                "https_port": svc.get("https_port", 443),
            })
        
        return services
    
    async def list_php_profiles(self) -> List[Dict[str, Any]]:
        """List PHP profiles available in Web Station."""
        try:
            data = await self._api_request(
                "SYNO.WebStation.PHP",
                "list",
            )
        except SynologyAPIError as e:
            if e.error_code == 102:
                raise SynologyAPIError("Web Station is not installed")
            raise
        
        profiles = []
        for profile in data.get("profiles", []):
            profiles.append({
                "id": profile.get("id", ""),
                "display_name": profile.get("display_name", ""),
                "version": profile.get("version", ""),
                "enable": profile.get("enable", False),
            })
        
        return profiles
    
    async def get_webstation_status(self) -> Dict[str, Any]:
        """Get Web Station status and configuration."""
        try:
            data = await self._api_request(
                "SYNO.WebStation.Status",
                "get",
            )
        except SynologyAPIError as e:
            if e.error_code == 102:
                raise SynologyAPIError("Web Station is not installed")
            raise
        
        return {
            "nginx_status": data.get("nginx", {}).get("status", "unknown"),
            "apache_status": data.get("apache", {}).get("status", "unknown"),
            "php_status": data.get("php", {}).get("status", "unknown"),
        }
    
    # -------------------------------------------------------------------------
    # Network Configuration
    # -------------------------------------------------------------------------
    
    async def get_network_config(self) -> Dict[str, Any]:
        """Get network configuration."""
        data = await self._api_request(
            "SYNO.Core.Network",
            "get",
        )
        
        return {
            "hostname": data.get("hostname", ""),
            "workgroup": data.get("workgroup", ""),
            "dns": data.get("dns", []),
            "gateway": data.get("gateway", ""),
        }
    
    async def list_network_interfaces(self) -> List[Dict[str, Any]]:
        """List network interfaces."""
        data = await self._api_request(
            "SYNO.Core.Network.Interface",
            "list",
        )
        
        interfaces = []
        for iface in data.get("interfaces", []):
            interfaces.append({
                "id": iface.get("id", ""),
                "name": iface.get("name", ""),
                "ip": iface.get("ip", ""),
                "mask": iface.get("mask", ""),
                "mac": iface.get("mac", ""),
                "type": iface.get("type", ""),
                "status": iface.get("status", ""),
            })
        
        return interfaces
    
    # -------------------------------------------------------------------------
    # Security Settings
    # -------------------------------------------------------------------------
    
    async def get_security_settings(self) -> Dict[str, Any]:
        """Get security settings."""
        data = await self._api_request(
            "SYNO.Core.Security.DSM",
            "get",
        )
        
        return {
            "logout_timer": data.get("logout_timer", 0),
            "trust_ip_check": data.get("trust_ip_check", False),
            "http_compression": data.get("http_compression", False),
            "cross_origin_request": data.get("cross_origin_request", False),
        }
    
    async def list_firewall_rules(self) -> List[Dict[str, Any]]:
        """List firewall rules."""
        data = await self._api_request(
            "SYNO.Core.Security.Firewall.Rules",
            "list",
        )
        
        rules = []
        for rule in data.get("rules", []):
            rules.append({
                "name": rule.get("name", ""),
                "action": rule.get("action", ""),
                "protocol": rule.get("protocol", ""),
                "ports": rule.get("ports", ""),
                "source_ip": rule.get("source_ip", ""),
                "enabled": rule.get("enabled", False),
            })
        
        return rules
    
    async def get_autoblock_settings(self) -> Dict[str, Any]:
        """Get auto-block settings."""
        data = await self._api_request(
            "SYNO.Core.Security.AutoBlock",
            "get",
        )
        
        return {
            "enabled": data.get("enable", False),
            "attempts": data.get("attempts", 0),
            "within_minutes": data.get("within_minutes", 0),
            "expire_days": data.get("expire_days", 0),
            "blocked_count": data.get("blocked_count", 0),
        }
    
    async def list_blocked_ips(self) -> List[Dict[str, Any]]:
        """List blocked IP addresses."""
        data = await self._api_request(
            "SYNO.Core.Security.AutoBlock.Rules",
            "list",
        )
        
        blocked = []
        for ip in data.get("rules", []):
            blocked.append({
                "ip": ip.get("ip", ""),
                "block_time": ip.get("block_time", 0),
                "expire_time": ip.get("expire_time", 0),
            })
        
        return blocked
    
    async def run_security_scan(self) -> Dict[str, Any]:
        """Run security advisor scan."""
        data = await self._api_request(
            "SYNO.Core.SecurityScan.Conf",
            "start",
        )
        
        return {
            "task_id": data.get("task_id", ""),
            "status": "started",
        }
    
    # -------------------------------------------------------------------------
    # Task Scheduler
    # -------------------------------------------------------------------------
    
    async def list_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """List scheduled tasks."""
        data = await self._api_request(
            "SYNO.Core.TaskScheduler",
            "list",
        )
        
        tasks = []
        for task in data.get("tasks", []):
            tasks.append({
                "id": task.get("id", 0),
                "name": task.get("name", ""),
                "type": task.get("type", ""),
                "enable": task.get("enable", False),
                "next_trigger_time": task.get("next_trigger_time", 0),
                "last_work_time": task.get("last_work_time", 0),
                "status": task.get("status", ""),
            })
        
        return tasks
    
    async def run_scheduled_task(self, task_id: int) -> bool:
        """Run a scheduled task immediately."""
        await self._api_request(
            "SYNO.Core.TaskScheduler",
            "run",
            id=task_id,
        )
        return True
    
    async def enable_scheduled_task(self, task_id: int, enabled: bool = True) -> bool:
        """Enable or disable a scheduled task."""
        await self._api_request(
            "SYNO.Core.TaskScheduler",
            "set",
            id=task_id,
            enable=enabled,
        )
        return True
    
    # -------------------------------------------------------------------------
    # Docker / Container Manager
    # -------------------------------------------------------------------------
    
    async def list_docker_containers(self) -> List[Dict[str, Any]]:
        """List Docker containers."""
        try:
            data = await self._api_request(
                "SYNO.Docker.Container",
                "list",
            )
        except SynologyAPIError as e:
            if e.error_code == 102:
                raise SynologyAPIError("Docker/Container Manager is not installed")
            raise
        
        containers = []
        for container in data.get("containers", []):
            containers.append({
                "id": container.get("id", ""),
                "name": container.get("name", ""),
                "image": container.get("image", ""),
                "status": container.get("status", ""),
                "state": container.get("state", ""),
                "created": container.get("created", 0),
            })
        
        return containers
    
    async def get_docker_container_info(self, container_id: str) -> Dict[str, Any]:
        """Get Docker container details."""
        data = await self._api_request(
            "SYNO.Docker.Container",
            "get",
            id=container_id,
        )
        
        return data.get("container", {})
    
    async def start_docker_container(self, container_id: str) -> bool:
        """Start a Docker container."""
        await self._api_request(
            "SYNO.Docker.Container",
            "start",
            id=container_id,
        )
        return True
    
    async def stop_docker_container(self, container_id: str) -> bool:
        """Stop a Docker container."""
        await self._api_request(
            "SYNO.Docker.Container",
            "stop",
            id=container_id,
        )
        return True
    
    async def restart_docker_container(self, container_id: str) -> bool:
        """Restart a Docker container."""
        await self._api_request(
            "SYNO.Docker.Container",
            "restart",
            id=container_id,
        )
        return True
    
    async def list_docker_images(self) -> List[Dict[str, Any]]:
        """List Docker images."""
        try:
            data = await self._api_request(
                "SYNO.Docker.Image",
                "list",
            )
        except SynologyAPIError as e:
            if e.error_code == 102:
                raise SynologyAPIError("Docker/Container Manager is not installed")
            raise
        
        images = []
        for image in data.get("images", []):
            images.append({
                "id": image.get("id", ""),
                "repository": image.get("repository", ""),
                "tag": image.get("tag", ""),
                "size": image.get("size", 0),
                "created": image.get("created", 0),
            })
        
        return images
    
    # -------------------------------------------------------------------------
    # Virtual Machine Manager
    # -------------------------------------------------------------------------
    
    async def list_virtual_machines(self) -> List[Dict[str, Any]]:
        """List virtual machines."""
        try:
            data = await self._api_request(
                "SYNO.Virtualization.Guest",
                "list",
            )
        except SynologyAPIError as e:
            if e.error_code == 102:
                raise SynologyAPIError("Virtual Machine Manager is not installed")
            raise
        
        vms = []
        for vm in data.get("guests", []):
            vms.append({
                "guest_id": vm.get("guest_id", ""),
                "guest_name": vm.get("guest_name", ""),
                "status": vm.get("status", ""),
                "vcpu_num": vm.get("vcpu_num", 0),
                "vram_size": vm.get("vram_size", 0),
                "autorun": vm.get("autorun", 0),
            })
        
        return vms
    
    async def get_vm_info(self, guest_id: str) -> Dict[str, Any]:
        """Get virtual machine details."""
        data = await self._api_request(
            "SYNO.Virtualization.Guest",
            "get",
            guest_id=guest_id,
        )
        
        return data.get("guest", {})
    
    async def start_vm(self, guest_id: str) -> bool:
        """Start a virtual machine."""
        await self._api_request(
            "SYNO.Virtualization.Guest",
            "poweron",
            guest_id=guest_id,
        )
        return True
    
    async def stop_vm(self, guest_id: str, force: bool = False) -> bool:
        """Stop a virtual machine."""
        method = "poweroff" if force else "shutdown"
        await self._api_request(
            "SYNO.Virtualization.Guest",
            method,
            guest_id=guest_id,
        )
        return True
    
    # -------------------------------------------------------------------------
    # Synology Photos
    # -------------------------------------------------------------------------
    
    async def list_photo_albums(self) -> List[Dict[str, Any]]:
        """List photo albums in Synology Photos."""
        try:
            data = await self._api_request(
                "SYNO.Foto.Browse.Album",
                "list",
                offset=0,
                limit=100,
            )
        except SynologyAPIError as e:
            if e.error_code == 102:
                raise SynologyAPIError("Synology Photos is not installed")
            raise
        
        albums = []
        for album in data.get("list", []):
            albums.append({
                "id": album.get("id", 0),
                "name": album.get("name", ""),
                "item_count": album.get("item_count", 0),
                "create_time": album.get("create_time", 0),
                "type": album.get("type", ""),
            })
        
        return albums
    
    # -------------------------------------------------------------------------
    # Synology Drive
    # -------------------------------------------------------------------------
    
    async def get_drive_status(self) -> Dict[str, Any]:
        """Get Synology Drive status."""
        try:
            data = await self._api_request(
                "SYNO.SynologyDrive.Info",
                "get",
            )
        except SynologyAPIError as e:
            if e.error_code == 102:
                raise SynologyAPIError("Synology Drive is not installed")
            raise
        
        return {
            "version": data.get("version", ""),
            "status": data.get("status", ""),
        }
    
    async def list_drive_team_folders(self) -> List[Dict[str, Any]]:
        """List Synology Drive team folders."""
        try:
            data = await self._api_request(
                "SYNO.SynologyDrive.TeamFolders",
                "list",
            )
        except SynologyAPIError as e:
            if e.error_code == 102:
                raise SynologyAPIError("Synology Drive is not installed")
            raise
        
        folders = []
        for folder in data.get("team_folders", []):
            folders.append({
                "id": folder.get("id", ""),
                "name": folder.get("name", ""),
                "share_name": folder.get("share_name", ""),
                "enable_version": folder.get("enable_version", False),
            })
        
        return folders
    
    # -------------------------------------------------------------------------
    # Log Center
    # -------------------------------------------------------------------------
    
    async def list_logs(
        self,
        log_type: str = "connection",
        offset: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List system logs.
        
        Args:
            log_type: Type of logs (connection, transfer, etc.)
            offset: Starting offset
            limit: Maximum logs to return
            
        Returns:
            List of log entries
        """
        data = await self._api_request(
            "SYNO.Core.SyslogClient.Log",
            "list",
            logtype=log_type,
            offset=offset,
            limit=limit,
        )
        
        logs = []
        for log in data.get("logs", []):
            logs.append({
                "time": log.get("time", 0),
                "user": log.get("user", ""),
                "event": log.get("event", ""),
                "ip": log.get("ip", ""),
                "desc": log.get("desc", ""),
            })
        
        return logs
    
    # -------------------------------------------------------------------------
    # Resource Monitor
    # -------------------------------------------------------------------------
    
    async def get_resource_usage(self) -> Dict[str, Any]:
        """Get current resource usage."""
        data = await self._api_request(
            "SYNO.Core.System.Utilization",
            "get",
        )
        
        cpu = data.get("cpu", {})
        memory = data.get("memory", {})
        network = data.get("network", [])
        disk = data.get("disk", {})
        
        return {
            "cpu": {
                "user_load": cpu.get("user_load", 0),
                "system_load": cpu.get("system_load", 0),
                "total_load": cpu.get("user_load", 0) + cpu.get("system_load", 0),
            },
            "memory": {
                "total_real": memory.get("memory_size", 0),
                "avail_real": memory.get("avail_real", 0),
                "real_usage": memory.get("real_usage", 0),
                "total_swap": memory.get("total_swap", 0),
                "avail_swap": memory.get("avail_swap", 0),
            },
            "network": [
                {
                    "device": iface.get("device", ""),
                    "rx": iface.get("rx", 0),
                    "tx": iface.get("tx", 0),
                }
                for iface in network
            ],
            "disk": {
                "read_access": disk.get("read_access", 0),
                "write_access": disk.get("write_access", 0),
                "utilization": disk.get("utilization", 0),
            },
        }
