"""URL parsing with automatic punycode decoding."""

from __future__ import annotations

import encodings.idna
from urllib.parse import ParseResult
from urllib.parse import urlparse as original_urlparse


def urlparse(url: str, scheme: str = "", allow_fragments: bool = True) -> ParseResult:
    """Parse a URL into 6 components, converting punycode domains to Unicode.

    This is a wrapper around urllib.parse.urlparse that automatically converts
    punycode-encoded domain names (xn--...) to their Unicode representation.
    """
    # First get the normal parsed result
    parsed = original_urlparse(url, scheme, allow_fragments)

    # If there's no netloc, return the original result
    if not parsed.netloc:
        return parsed

    try:
        # Split netloc into parts (user:pass@host:port)
        userinfo = ""
        host = parsed.netloc
        port = ""

        # Extract userinfo if present
        if "@" in host:
            userinfo, host = host.rsplit("@", 1)
            userinfo += "@"

        # Extract port if present
        if ":" in host:
            host, port = host.rsplit(":", 1)
            port = ":" + port

        # Decode punycode domains
        if host.startswith("xn--"):
            # Use stdlib's encodings.idna to decode
            # Need to decode each part separately for domains with multiple labels
            decoded_parts = [
                encodings.idna.ToUnicode(part) if part.startswith("xn--") else part
                for part in host.split(".")
            ]
            decoded_host = ".".join(decoded_parts)

            # Create new netloc with decoded host
            new_netloc = f"{userinfo}{decoded_host}{port}"

            # Create new parsed result with decoded netloc
            return ParseResult(
                scheme=parsed.scheme,
                netloc=new_netloc,
                path=parsed.path,
                params=parsed.params,
                query=parsed.query,
                fragment=parsed.fragment,
            )
    except Exception:  # noqa: S110
        # If anything goes wrong during decoding, return original
        pass

    return parsed
