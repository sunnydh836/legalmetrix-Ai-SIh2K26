import os
import uuid
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageServiceInterface(ABC):
    """Abstract interface for file and object storage backends."""

    @abstractmethod
    def save_file(
        self,
        file_bytes: bytes,
        scan_id: str,
        extension: str,
        custom_filename: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Save file bytes into storage under the given scan namespace.
        Returns a tuple of (relative_file_path, stored_filename).
        """
        pass

    @abstractmethod
    def delete_file(self, relative_path: str) -> bool:
        """
        Delete a file by its relative storage path.
        Returns True if deleted or already absent, False on failure.
        """
        pass

    @abstractmethod
    def get_file_path(self, relative_path: str) -> Path:
        """
        Get absolute Path for a given relative storage path.
        Guarantees path traversal protection.
        """
        pass

    @abstractmethod
    def exists(self, relative_path: str) -> bool:
        """Check if a file exists in storage."""
        pass


class LocalStorageService(StorageServiceInterface):
    """
    Local filesystem storage implementation for LegalMetrix AI.
    Stores files under: <base_storage_dir>/scans/<scan_id>/<uuid>.<ext>
    """

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.base_path = Path(base_dir).resolve()
        else:
            # Default to settings.LOCAL_STORAGE_PATH relative to backend root
            backend_root = Path(__file__).resolve().parent.parent.parent
            self.base_path = (backend_root / settings.LOCAL_STORAGE_PATH).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, relative_path: str) -> Path:
        """Resolve path and verify it is strictly within the base storage directory."""
        clean_rel = os.path.normpath(relative_path).lstrip(r"\/")
        full_path = (self.base_path / clean_rel).resolve()
        if not str(full_path).startswith(str(self.base_path)):
            raise ValueError(f"Path traversal detected: {relative_path}")
        return full_path

    def save_file(
        self,
        file_bytes: bytes,
        scan_id: str,
        extension: str,
        custom_filename: Optional[str] = None,
    ) -> Tuple[str, str]:
        # Sanitize extension
        clean_ext = extension.lstrip(".").lower()
        if not clean_ext:
            clean_ext = "jpg"

        # Generate safe stored filename
        if custom_filename:
            stored_filename = os.path.basename(custom_filename)
        else:
            stored_filename = f"{uuid.uuid4().hex}.{clean_ext}"

        # Clean scan_id for path
        safe_scan_id = "".join(c for c in scan_id if c.isalnum() or c in ("-", "_"))
        if not safe_scan_id:
            safe_scan_id = "default"

        rel_dir = os.path.join("scans", safe_scan_id)
        target_dir = self.base_path / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        full_file_path = target_dir / stored_filename
        # Verify safe path
        if not str(full_file_path.resolve()).startswith(str(self.base_path)):
            raise ValueError(f"Invalid storage path generated for scan {scan_id}")

        with open(full_file_path, "wb") as f:
            f.write(file_bytes)

        relative_path = os.path.join(rel_dir, stored_filename).replace("\\", "/")
        return relative_path, stored_filename

    def delete_file(self, relative_path: str) -> bool:
        try:
            full_path = self._resolve_safe_path(relative_path)
            if full_path.exists() and full_path.is_file():
                full_path.unlink()
                logger.info(f"Deleted storage file: {relative_path}")
            return True
        except Exception as e:
            logger.error(f"Error deleting storage file {relative_path}: {e}")
            return False

    def get_file_path(self, relative_path: str) -> Path:
        full_path = self._resolve_safe_path(relative_path)
        if not full_path.exists():
            raise FileNotFoundError(f"Storage file not found: {relative_path}")
        return full_path

    def exists(self, relative_path: str) -> bool:
        try:
            full_path = self._resolve_safe_path(relative_path)
            return full_path.exists() and full_path.is_file()
        except Exception:
            return False


_storage_service_instance: Optional[StorageServiceInterface] = None


def get_storage_service() -> StorageServiceInterface:
    """Dependency provider for storage service singleton."""
    global _storage_service_instance
    if _storage_service_instance is None:
        _storage_service_instance = LocalStorageService()
    return _storage_service_instance
