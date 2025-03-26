def normalize_url(url: str) -> str | None:
    """Normalize URLs to a canonical form.

    - Removes trailing slashes
    - Removes protocol (http/https)
    - Removes www.
    - Lowercases the domain
    - Preserves path case (as it may be significant)
    - Returns None if protocol is invalid (not http/https)
    """
    url = url.strip()

    # Validate and remove protocol
    if "://" in url:
        protocol, rest = url.split("://", 1)
        if protocol.lower() not in ("http", "https"):
            return None
        url = rest

    # Remove www.
    if url.startswith("www."):
        url = url[4:]

    # Split domain and path
    parts = url.split("/", 1)
    domain = parts[0].lower()
    path = parts[1] if len(parts) > 1 else ""

    # Combine and remove trailing slash
    full = f"{domain}/{path}" if path else domain
    return full.rstrip("/")
