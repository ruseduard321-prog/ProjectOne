"""Storage adapter implementations.

Everything vendor-specific lives here and nowhere above it. A `boto3` type, a
`botocore` exception or an endpoint URL appearing outside this package is an
architectural regression, asserted against by
`tests/test_storage_boundary.py`.
"""
