"""
NDJSON resource generation for Telegram Toolkit MCP.

This module provides efficient handling of large datasets through NDJSON
(Newline Delimited JSON) resources, enabling streaming and pagination
of message data for MCP clients.
"""

import asyncio
import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, AsyncGenerator

try:
    from mcp import Resource, ResourceTemplate
except ImportError:
    # Fallback for development
    Resource = dict
    ResourceTemplate = dict

from ..utils.logging import get_logger

logger = get_logger(__name__)


class NDJSONResourceManager:
    """
    Manager for NDJSON resources and temporary files.

    Handles creation, cleanup, and serving of large dataset exports
    as NDJSON resources for MCP clients.
    """

    def __init__(self, temp_dir: Optional[str] = None, max_age_hours: int = 24):
        """
        Initialize resource manager.

        Args:
            temp_dir: Directory for temporary files
            max_age_hours: Maximum age of resource files before cleanup
        """
        self.temp_dir = Path(temp_dir or tempfile.gettempdir()) / "mcp-resources"
        self.temp_dir.mkdir(exist_ok=True)
        self.max_age_hours = max_age_hours
        self.active_resources: Dict[str, Dict[str, Any]] = {}

        logger.info("NDJSON resource manager initialized", temp_dir=str(self.temp_dir))

    def generate_resource_id(self) -> str:
        """
        Generate unique resource ID.

        Returns:
            str: Unique resource identifier
        """
        return f"export-{uuid.uuid4().hex[:16]}"

    def get_resource_path(self, resource_id: str) -> Path:
        """
        Get filesystem path for resource.

        Args:
            resource_id: Resource identifier

        Returns:
            Path: Filesystem path for the resource
        """
        return self.temp_dir / f"{resource_id}.ndjson"

    async def create_ndjson_resource(
        self,
        data: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
        resource_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create NDJSON resource from data.

        Args:
            data: List of data items to serialize
            metadata: Optional metadata for the resource
            resource_id: Optional custom resource ID

        Returns:
            Dict containing resource information
        """
        if not data:
            raise ValueError("Cannot create resource from empty data")

        resource_id = resource_id or self.generate_resource_id()
        file_path = self.get_resource_path(resource_id)

        try:
            # Write data to NDJSON file
            await self._write_ndjson_file(file_path, data)

            # Create resource metadata
            resource_info = {
                "resource_id": resource_id,
                "uri": f"mcp://resources/export/{resource_id}.ndjson",
                "path": str(file_path),
                "format": "ndjson",
                "item_count": len(data),
                "file_size": file_path.stat().st_size,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(hours=self.max_age_hours)).isoformat(),
                "metadata": metadata or {}
            }

            # Store resource info
            self.active_resources[resource_id] = resource_info

            logger.info(
                "NDJSON resource created",
                resource_id=resource_id,
                item_count=len(data),
                file_size=resource_info["file_size"]
            )

            return resource_info

        except Exception as e:
            # Clean up on failure
            if file_path.exists():
                file_path.unlink()
            raise

    async def _write_ndjson_file(self, file_path: Path, data: List[Dict[str, Any]]) -> None:
        """
        Write data to NDJSON file.

        Args:
            file_path: Path to write the file
            data: Data to serialize
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for item in data:
                    # Ensure datetime objects are serialized properly
                    processed_item = self._process_item_for_json(item)
                    json_line = json.dumps(processed_item, ensure_ascii=False)
                    f.write(json_line + '\n')

        except Exception as e:
            logger.error("Failed to write NDJSON file", path=str(file_path), error=str(e))
            raise

    def _process_item_for_json(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process item for JSON serialization.

        Args:
            item: Item to process

        Returns:
            Processed item safe for JSON serialization
        """
        processed = {}

        for key, value in item.items():
            if isinstance(value, datetime):
                # Convert datetime to ISO format
                processed[key] = value.isoformat() + "Z"
            elif isinstance(value, (int, float, str, bool)) or value is None:
                # Keep primitive types as-is
                processed[key] = value
            elif isinstance(value, dict):
                # Recursively process nested dicts
                processed[key] = self._process_item_for_json(value)
            elif isinstance(value, list):
                # Process lists
                processed[key] = [
                    self._process_item_for_json(sub_item) if isinstance(sub_item, dict) else sub_item
                    for sub_item in value
                ]
            else:
                # Convert other types to string
                processed[key] = str(value)

        return processed

    async def read_ndjson_resource(self, resource_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Read NDJSON resource as async generator.

        Args:
            resource_id: Resource identifier

        Yields:
            Dict items from the NDJSON file
        """
        file_path = self.get_resource_path(resource_id)

        if not file_path.exists():
            raise FileNotFoundError(f"Resource {resource_id} not found")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        item = json.loads(line)
                        yield item
                    except json.JSONDecodeError as e:
                        logger.warning(
                            "Invalid JSON line in NDJSON file",
                            resource_id=resource_id,
                            line_num=line_num,
                            error=str(e)
                        )
                        continue

        except Exception as e:
            logger.error("Failed to read NDJSON resource", resource_id=resource_id, error=str(e))
            raise

    def get_resource_info(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a resource.

        Args:
            resource_id: Resource identifier

        Returns:
            Dict with resource information or None if not found
        """
        return self.active_resources.get(resource_id)

    def list_resources(self) -> List[Dict[str, Any]]:
        """
        List all active resources.

        Returns:
            List of resource information dictionaries
        """
        return list(self.active_resources.values())

    async def cleanup_expired_resources(self) -> int:
        """
        Clean up expired resource files.

        Returns:
            int: Number of files cleaned up
        """
        now = datetime.utcnow()
        expired_resources = []

        for resource_id, resource_info in self.active_resources.items():
            expires_at = datetime.fromisoformat(resource_info["expires_at"])
            if now > expires_at:
                expired_resources.append(resource_id)

        # Clean up expired resources
        cleaned_count = 0
        for resource_id in expired_resources:
            try:
                file_path = self.get_resource_path(resource_id)
                if file_path.exists():
                    file_path.unlink()
                    cleaned_count += 1

                # Remove from active resources
                del self.active_resources[resource_id]

                logger.info("Cleaned up expired resource", resource_id=resource_id)

            except Exception as e:
                logger.error(
                    "Failed to cleanup resource",
                    resource_id=resource_id,
                    error=str(e)
                )

        if cleaned_count > 0:
            logger.info("Resource cleanup completed", cleaned_count=cleaned_count)

        return cleaned_count

    def get_resource_stats(self) -> Dict[str, Any]:
        """
        Get resource usage statistics.

        Returns:
            Dict containing resource statistics
        """
        total_size = 0
        oldest_resource = None
        newest_resource = None

        for resource_info in self.active_resources.values():
            total_size += resource_info.get("file_size", 0)

            created_at = datetime.fromisoformat(resource_info["created_at"])
            if oldest_resource is None or created_at < oldest_resource:
                oldest_resource = created_at
            if newest_resource is None or created_at > newest_resource:
                newest_resource = created_at

        return {
            "active_resources": len(self.active_resources),
            "total_file_size": total_size,
            "oldest_resource": oldest_resource.isoformat() if oldest_resource else None,
            "newest_resource": newest_resource.isoformat() if newest_resource else None,
            "temp_dir": str(self.temp_dir)
        }


class MCPResourceAdapter:
    """
    Adapter for MCP resource integration.

    Provides MCP-compatible resource definitions and handlers
    for NDJSON resources.
    """

    def __init__(self, resource_manager: NDJSONResourceManager):
        """
        Initialize MCP resource adapter.

        Args:
            resource_manager: NDJSON resource manager instance
        """
        self.resource_manager = resource_manager

    def create_resource_template(self) -> Dict[str, Any]:
        """
        Create MCP resource template for NDJSON exports.

        Returns:
            Dict containing resource template definition
        """
        return {
            "uri_template": "mcp://resources/export/{resource_id}.ndjson",
            "name": "Telegram Message Export",
            "description": "NDJSON export of Telegram message data",
            "mime_type": "application/x-ndjson"
        }

    def create_resource_list(self) -> List[Dict[str, Any]]:
        """
        Create list of available MCP resources.

        Returns:
            List of MCP resource definitions
        """
        resources = []

        for resource_info in self.resource_manager.list_resources():
            resource = {
                "uri": resource_info["uri"],
                "name": f"Export {resource_info['resource_id']}",
                "description": (
                    f"NDJSON export with {resource_info['item_count']} items, "
                    f"created {resource_info['created_at']}"
                ),
                "mime_type": "application/x-ndjson",
                "metadata": {
                    "item_count": resource_info["item_count"],
                    "file_size": resource_info["file_size"],
                    "created_at": resource_info["created_at"],
                    "expires_at": resource_info["expires_at"]
                }
            }
            resources.append(resource)

        return resources

    async def handle_resource_request(self, uri: str) -> AsyncGenerator[str, None]:
        """
        Handle MCP resource request.

        Args:
            uri: Resource URI

        Yields:
            str: Lines of NDJSON data
        """
        # Parse URI to extract resource ID
        if not uri.startswith("mcp://resources/export/"):
            raise ValueError(f"Invalid resource URI: {uri}")

        resource_path = uri.replace("mcp://resources/export/", "")
        if not resource_path.endswith(".ndjson"):
            raise ValueError(f"Invalid resource format: {uri}")

        resource_id = resource_path.replace(".ndjson", "")

        # Stream the NDJSON data
        async for item in self.resource_manager.read_ndjson_resource(resource_id):
            # Convert back to JSON line
            json_line = json.dumps(item, ensure_ascii=False)
            yield json_line + "\n"


# Global resource manager instance
_resource_manager: Optional[NDJSONResourceManager] = None


def get_resource_manager() -> NDJSONResourceManager:
    """Get global resource manager instance."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = NDJSONResourceManager()
    return _resource_manager


# Export main classes and functions
__all__ = [
    "NDJSONResourceManager",
    "MCPResourceAdapter",
    "get_resource_manager"
]
