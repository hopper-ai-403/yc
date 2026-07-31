"""Storage provider abstraction.

Application code must depend on StorageProvider, never on boto3 directly.
"""

from app.shared.storage.provider import StorageProvider

__all__ = ["StorageProvider"]
