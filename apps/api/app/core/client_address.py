"""Resolving the real client address from behind a reverse proxy.

ProjectOne runs behind at least one proxy: `apps/web` proxies every browser
call so the access token can live in an httpOnly cookie the browser cannot read
(STEP-16). Production adds more -- a CDN, possibly an Nginx or Caddy sidecar.
The peer address the API sees is therefore the *proxy's*, not the client's, and
rate limiting a public endpoint by peer address limits the whole platform as
one caller (ADR-002).

The fix is not to trust `X-Forwarded-For`. That header is caller-supplied, and
counting against it unconditionally hands the limiter's key to the attacker: a
client that varies one header value gets an unlimited allowance while the logs
show a limiter working normally against thousands of distinct "clients".

**A forwarded header is trustworthy only when it arrives from a peer that is
itself trusted to have written it.** That is the whole idea here, and the peer
address -- the TCP source, which cannot be forged without controlling the
network path -- is what every trust decision anchors to.

This module is deliberately pure: addresses and headers in, an address out. It
holds no request object, no framework type and no I/O, so the parsing rules can
be tested exhaustively without constructing an HTTP request (ADR-002 §Task 2).
"""

import ipaddress
from collections.abc import Iterable, Sequence

#: The conventional multi-hop forwarding header.
#:
#: Appended to by each hop, so it accumulates left to right:
#: `client, proxy1, proxy2`. The leftmost entry is the one an attacker controls.
FORWARDED_FOR_HEADER = "x-forwarded-for"

#: How many entries of a forwarded chain are examined before giving up.
#:
#: A header is untrusted input and its length is attacker-chosen. Without a
#: ceiling, a caller could send tens of thousands of entries and make every
#: request perform that much parsing work -- cheap to send, linear to process.
#: Real chains are single digits; anything past this is not a deployment.
_MAX_CHAIN_ENTRIES = 32

#: Networks parsed once from configuration.
TrustedProxies = tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]


def parse_trusted_proxies(values: Iterable[str]) -> TrustedProxies:
    """Parse trusted-proxy CIDRs and bare addresses into networks.

    Bare addresses are accepted and become single-host networks, because a
    loopback sidecar is naturally written `127.0.0.1` rather than
    `127.0.0.1/32` and forcing the suffix would invite copy-paste errors in the
    one setting where an error is silent.

    Args:
        values: CIDR ranges or bare IP addresses, e.g. `("127.0.0.1",
            "173.245.48.0/20")`. Blank entries are ignored so a trailing comma
            in configuration is not an error.

    Returns:
        The parsed networks, in the order given.

    Raises:
        ValueError: if an entry is neither a valid network nor a valid address.
            Deliberately fatal: this is parsed at startup, and a typo that
            silently dropped one entry would narrow the allowlist without
            anyone noticing -- which restores the exact defect ADR-002 closes.
    """
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []

    for value in values:
        candidate = value.strip()

        if not candidate:
            continue

        try:
            networks.append(ipaddress.ip_network(candidate, strict=False))
        except ValueError as error:
            raise ValueError(
                f"Invalid trusted proxy entry {candidate!r}: expected an IP address or CIDR range"
            ) from error

    return tuple(networks)


def _parse_address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Return the address `value` denotes, or None if it is not one.

    Handles the shapes that appear in a real `X-Forwarded-For`: a bare address,
    an IPv6 address in brackets, and either with a `:port` suffix. Anything
    else -- including the `unknown` token the RFC permits, and the obfuscated
    identifiers `Forwarded` allows -- is not an address and yields None.
    """
    candidate = value.strip()

    if not candidate:
        return None

    # `[2001:db8::1]:443` or `[2001:db8::1]` -- the bracket form exists
    # precisely because a bare IPv6 address is full of colons and cannot
    # otherwise be told apart from a port suffix.
    if candidate.startswith("["):
        closing = candidate.find("]")

        if closing == -1:
            return None

        candidate = candidate[1:closing]
    elif candidate.count(":") == 1:
        # Exactly one colon means IPv4 with a port. More than one means a bare
        # IPv6 address, where splitting on the colon would corrupt it.
        candidate = candidate.split(":", 1)[0]

    try:
        return ipaddress.ip_address(candidate)
    except ValueError:
        return None


def _is_trusted(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    trusted: TrustedProxies,
) -> bool:
    """Report whether `address` falls inside any trusted network."""
    return any(address in network for network in trusted)


def resolve_client_address(
    peer: str | None,
    forwarded_for: str | None,
    trusted: TrustedProxies,
    platform_header: str | None = None,
) -> str:
    """Return the address a rate limit should be counted against.

    The rules, in order (ADR-002 §3):

    1. **No peer address** -- nothing can be trusted, so nothing is honoured.
       Returns `"unknown"`, which is a real bucket: unattributable requests
       share one allowance rather than escaping limiting entirely.
    2. **Peer is not trusted** -- every forwarded header is ignored and the peer
       address is used. This is the internet-facing case, and it is what stops a
       forged header from ever becoming a limiter key.
    3. **Peer is trusted and a platform header is present** -- honour it. A
       single-hop, non-appendable header (Cloudflare's `CF-Connecting-IP`) is
       trustworthy *because the platform overwrites it*, which holds only
       because the request demonstrably came from that platform.
    4. **Peer is trusted** -- walk `X-Forwarded-For` right to left, discarding
       entries that are themselves trusted proxies. The first untrusted address
       is the client.
    5. **Every entry is trusted, or the header is absent or malformed** -- fall
       back to the peer address.

    Never the leftmost entry. Honest proxies *append*, and a client may send the
    header itself, so the leftmost value is whatever the caller chose to put
    there. Taking it is the classic vulnerability in this area, and it fails
    silently -- which is worse than not parsing the header at all.

    Failure is closed throughout: every path returns *some* key, so a malformed
    header or absent configuration produces a weaker limit, never no limit.

    Args:
        peer: The immediate peer address (the TCP source).
        forwarded_for: Raw `X-Forwarded-For` value, if the request carried one.
        trusted: Networks whose members may set forwarding headers.
        platform_header: Raw value of the configured single-hop platform header,
            if one is configured and the request carried it.

    Returns:
        The client address as a string, or `"unknown"` when there is no peer.
    """
    if peer is None:
        return "unknown"

    peer_address = _parse_address(peer)

    # An unparseable peer cannot be matched against the allowlist, so it cannot
    # be trusted. Returned verbatim so it still forms a stable bucket.
    if peer_address is None:
        return peer

    if not _is_trusted(peer_address, trusted):
        return peer

    if platform_header is not None:
        platform_address = _parse_address(platform_header)

        if platform_address is not None:
            return str(platform_address)

    if forwarded_for is None:
        return str(peer_address)

    # Bounded before reversing: slicing the *tail* is what a right-to-left walk
    # actually reads, so an oversized header is truncated at the end a
    # padding attack would target rather than the end that holds the client.
    entries: Sequence[str] = forwarded_for.split(",")[-_MAX_CHAIN_ENTRIES:]

    for entry in reversed(entries):
        address = _parse_address(entry)

        if address is None:
            # A malformed entry invalidates the chain: everything to its left is
            # unverifiable, because the hop that should have written a real
            # address did not. Falling back is safer than skipping it and
            # trusting whatever sits further left.
            return str(peer_address)

        if not _is_trusted(address, trusted):
            return str(address)

    return str(peer_address)
