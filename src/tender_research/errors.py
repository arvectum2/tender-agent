from __future__ import annotations


class TenderResearchError(Exception):
    pass


class IngestCheckpointConflictError(TenderResearchError):
    pass


class DocumentIdentityConflictError(TenderResearchError):
    pass


class EisLoaderError(TenderResearchError):
    pass


class EisMissingTokenError(EisLoaderError):
    pass


class EisAuthFailedError(EisLoaderError):
    pass


class EisConnectionResetError(EisLoaderError):
    pass


class EisNoDataError(EisLoaderError):
    pass


class EisMethodNotAvailableError(EisLoaderError):
    pass


class EisParseError(EisLoaderError):
    pass


def classify_eis_error(exc: Exception) -> EisLoaderError:
    msg = str(exc).lower()
    if "connection reset by peer" in msg or "errno 54" in msg or "errno 104" in msg:
        return EisConnectionResetError(str(exc))
    if "not configured" in msg or "token" in msg.lower():
        return EisMissingTokenError(str(exc))
    if "auth" in msg or "unauthorized" in msg or "forbidden" in msg or "403" in msg or "401" in msg:
        return EisAuthFailedError(str(exc))
    if "no_data" in msg or "no archive" in msg or "not found" in msg:
        return EisNoDataError(str(exc))
    if "parse" in msg or "xml" in msg:
        return EisParseError(str(exc))
    return EisLoaderError(str(exc))


class DocumentStoreError(TenderResearchError):
    pass


class SearchProviderError(TenderResearchError):
    pass


class FetchError(TenderResearchError):
    pass


class RateLimitError(TenderResearchError):
    pass


class DiscoveryError(TenderResearchError):
    pass


class DiscoveryEmptyError(DiscoveryError):
    pass
