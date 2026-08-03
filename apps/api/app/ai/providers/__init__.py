"""Provider adapters.

One module per provider, each translating its vendor's wire format and failures
into the common contract in `app.ai.provider` and `app.ai.errors`. Nothing
outside this package imports a vendor's field names.
"""
