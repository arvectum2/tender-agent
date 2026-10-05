"""Compatibility facade for the shared Data Platform consumer SDK.

New cross-product HTTP behavior lives in the standalone arvectum-data-client
distribution. Keeping this module preserves Tender Agent and Arvectum OS import
paths while removing the duplicated transport implementation.
"""

from arvectum_data_client import (
    DataPlatformClient,
    DataPlatformError,
    DataPlatformHttpClient,
    SearchProfile,
    build_collection_id,
)

__all__ = [
    "DataPlatformClient",
    "DataPlatformError",
    "DataPlatformHttpClient",
    "SearchProfile",
    "build_collection_id",
]
