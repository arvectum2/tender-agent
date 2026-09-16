# Integration outbox v1
Repository-owned transactional outbox for internal integration events. The v1 envelope exposes only workflow metadata and strips credential-like keys recursively. Listing/export is read-only and tenant-filterable.

Live email, webhook, CRM, messenger or other external delivery is intentionally **disabled**. `/integration-outbox/adapter-status` is fail-closed and cannot enable a transport. Enabling a destination, credential, network delivery, or external side effect requires a separate REVIEW/HUMAN gate.
