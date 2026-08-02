"""Client address resolution behind a reverse proxy (ADR-002 §3).

These are the security tests for the trust boundary. The parsing rules here are
a well-known source of real vulnerabilities -- taking the leftmost
`X-Forwarded-For` entry is the classic one -- so each rule is asserted
explicitly rather than inferred from a happy-path case.

Pure functions, no HTTP: `resolve_client_address` takes addresses and headers
and returns an address, which is exactly why it was built as a separate unit.
"""

import pytest

from app.core.client_address import parse_trusted_proxies, resolve_client_address

#: A proxy the API trusts, and the network it belongs to.
PROXY = "10.0.0.5"
TRUSTED = parse_trusted_proxies(["10.0.0.0/8", "127.0.0.1"])

#: An address outside every trusted range -- the internet.
OUTSIDER = "203.0.113.9"


# ---------------------------------------------------------------------------
# The security property: a forged header from an untrusted peer is ignored
# ---------------------------------------------------------------------------


def test_a_forged_header_from_an_untrusted_peer_is_ignored() -> None:
    """The single most important assertion in this module.

    An attacker connecting directly to the API sends whatever they like in
    `X-Forwarded-For`. If that value became the rate limit key, they would hold
    an unlimited allowance -- a limiter the attacker controls, which is worse
    than no limiter because the logs would look healthy.
    """
    resolved = resolve_client_address(
        peer=OUTSIDER,
        forwarded_for="1.2.3.4",
        trusted=TRUSTED,
    )

    assert resolved == OUTSIDER, "a forged header must never become the key"


def test_an_untrusted_peer_cannot_spoof_via_a_long_chain() -> None:
    """Padding the chain with plausible hops does not buy trust either."""
    resolved = resolve_client_address(
        peer=OUTSIDER,
        forwarded_for="1.2.3.4, 10.0.0.5, 127.0.0.1",
        trusted=TRUSTED,
    )

    assert resolved == OUTSIDER


def test_an_empty_allowlist_trusts_nothing() -> None:
    """Absent configuration must fail closed, not open.

    An empty allowlist is the default. It has to degrade to peer-address
    limiting -- weaker but unforgeable -- rather than to honouring headers.
    """
    resolved = resolve_client_address(
        peer=PROXY,
        forwarded_for="1.2.3.4",
        trusted=(),
    )

    assert resolved == PROXY


# ---------------------------------------------------------------------------
# Honouring a header from a peer that is actually trusted
# ---------------------------------------------------------------------------


def test_a_trusted_peer_forwarding_one_client_is_honoured() -> None:
    """The ordinary case: Next.js proxying a browser."""
    resolved = resolve_client_address(
        peer=PROXY,
        forwarded_for=OUTSIDER,
        trusted=TRUSTED,
    )

    assert resolved == OUTSIDER


def test_the_chain_is_walked_right_to_left() -> None:
    """Two trusted hops in front of the client, appended in order."""
    resolved = resolve_client_address(
        peer=PROXY,
        forwarded_for=f"{OUTSIDER}, 10.0.0.7, 10.0.0.5",
        trusted=TRUSTED,
    )

    assert resolved == OUTSIDER


def test_a_client_supplied_leftmost_entry_is_not_taken() -> None:
    """The vulnerability this parsing order exists to prevent.

    A client may send `X-Forwarded-For` itself, and an honest proxy *appends*
    rather than replacing -- so the real client address ends up in the middle
    and the leftmost entry is whatever the attacker chose. Reading left-to-right
    would take the forgery.
    """
    resolved = resolve_client_address(
        peer=PROXY,
        # The attacker sent "9.9.9.9"; the proxy appended what it actually saw.
        forwarded_for=f"9.9.9.9, {OUTSIDER}, 10.0.0.5",
        trusted=TRUSTED,
    )

    assert resolved == OUTSIDER, "the first untrusted address from the right is the client"
    assert resolved != "9.9.9.9", "the leftmost entry must never win"


def test_a_chain_of_only_trusted_proxies_falls_back_to_the_peer() -> None:
    """No untrusted entry means no client was ever recorded."""
    resolved = resolve_client_address(
        peer=PROXY,
        forwarded_for="10.0.0.7, 10.0.0.5",
        trusted=TRUSTED,
    )

    assert resolved == PROXY


# ---------------------------------------------------------------------------
# Failing closed on malformed input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "forwarded",
    [
        "not-an-address",
        "",
        "   ",
        "unknown",
        "1.2.3.4, garbage",
        "999.999.999.999",
    ],
)
def test_a_malformed_chain_falls_back_to_the_peer(forwarded: str) -> None:
    """Malformed input never escapes limiting; it only weakens the key."""
    resolved = resolve_client_address(
        peer=PROXY,
        forwarded_for=forwarded,
        trusted=TRUSTED,
    )

    assert resolved == PROXY


def test_an_absent_header_falls_back_to_the_peer() -> None:
    resolved = resolve_client_address(peer=PROXY, forwarded_for=None, trusted=TRUSTED)

    assert resolved == PROXY


def test_no_peer_yields_a_shared_bucket_rather_than_no_limit() -> None:
    """Unattributable requests share one allowance instead of escaping."""
    resolved = resolve_client_address(peer=None, forwarded_for=OUTSIDER, trusted=TRUSTED)

    assert resolved == "unknown"


def test_an_oversized_chain_is_bounded() -> None:
    """A padded header must not make every request do unbounded parsing work.

    The tail is what a right-to-left walk reads, so truncation keeps the entries
    that matter and discards the padding.
    """
    padding = ", ".join(["10.0.0.7"] * 500)

    resolved = resolve_client_address(
        peer=PROXY,
        forwarded_for=f"{OUTSIDER}, {padding}, 10.0.0.5",
        trusted=TRUSTED,
    )

    # Every entry within the bound is trusted, so it falls back to the peer --
    # the safe outcome. What matters is that it terminates and never returns
    # the attacker-controlled head.
    assert resolved == PROXY


# ---------------------------------------------------------------------------
# Address shapes that appear in real chains
# ---------------------------------------------------------------------------


def test_a_port_suffix_is_stripped() -> None:
    resolved = resolve_client_address(
        peer=PROXY,
        forwarded_for=f"{OUTSIDER}:51234",
        trusted=TRUSTED,
    )

    assert resolved == OUTSIDER


def test_a_bracketed_ipv6_address_is_parsed() -> None:
    resolved = resolve_client_address(
        peer=PROXY,
        forwarded_for="[2001:db8::1]:443",
        trusted=TRUSTED,
    )

    assert resolved == "2001:db8::1"


def test_a_bare_ipv6_address_is_not_split_on_its_colons() -> None:
    """The bracket form exists because a bare IPv6 address is full of colons."""
    resolved = resolve_client_address(
        peer=PROXY,
        forwarded_for="2001:db8::1",
        trusted=TRUSTED,
    )

    assert resolved == "2001:db8::1"


def test_entries_are_trimmed() -> None:
    resolved = resolve_client_address(
        peer=PROXY,
        forwarded_for=f"  {OUTSIDER}  ,  10.0.0.5  ",
        trusted=TRUSTED,
    )

    assert resolved == OUTSIDER


# ---------------------------------------------------------------------------
# The platform header override
# ---------------------------------------------------------------------------


def test_a_platform_header_from_a_trusted_peer_wins() -> None:
    """Cloudflare's CF-Connecting-IP is single-hop and non-appendable."""
    resolved = resolve_client_address(
        peer=PROXY,
        forwarded_for="10.0.0.7, 10.0.0.5",
        trusted=TRUSTED,
        platform_header=OUTSIDER,
    )

    assert resolved == OUTSIDER


def test_a_platform_header_from_an_untrusted_peer_is_ignored() -> None:
    """It is trustworthy only *because* the platform overwrites it.

    That guarantee holds only if the request came from the platform, so the
    same trust gate applies as to any other forwarding header.
    """
    resolved = resolve_client_address(
        peer=OUTSIDER,
        forwarded_for=None,
        trusted=TRUSTED,
        platform_header="1.2.3.4",
    )

    assert resolved == OUTSIDER


def test_a_malformed_platform_header_falls_through_to_the_chain() -> None:
    resolved = resolve_client_address(
        peer=PROXY,
        forwarded_for=OUTSIDER,
        trusted=TRUSTED,
        platform_header="not-an-address",
    )

    assert resolved == OUTSIDER


# ---------------------------------------------------------------------------
# Allowlist parsing
# ---------------------------------------------------------------------------


def test_bare_addresses_and_cidrs_are_both_accepted() -> None:
    networks = parse_trusted_proxies(["127.0.0.1", "10.0.0.0/8", "::1"])

    assert len(networks) == 3


def test_blank_entries_are_ignored() -> None:
    """A trailing comma in configuration is not an error."""
    assert parse_trusted_proxies(["127.0.0.1", "", "  "]) == parse_trusted_proxies(["127.0.0.1"])


def test_a_malformed_entry_is_rejected_loudly() -> None:
    """Silently dropping it would narrow the allowlist with no signal."""
    with pytest.raises(ValueError, match="Invalid trusted proxy entry"):
        parse_trusted_proxies(["10.0.0.0/8", "not-a-network"])


def test_ipv6_trust_is_matched_by_range() -> None:
    trusted = parse_trusted_proxies(["2001:db8::/32"])

    resolved = resolve_client_address(
        peer="2001:db8::5",
        forwarded_for=OUTSIDER,
        trusted=trusted,
    )

    assert resolved == OUTSIDER
