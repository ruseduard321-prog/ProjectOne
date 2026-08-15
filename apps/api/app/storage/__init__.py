"""Object storage, behind a vendor-neutral boundary.

The public surface is `StorageProvider` and the value types around it. Adapters
live in `app/storage/providers/` and nothing outside this package imports them
directly ([[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]]).
"""
