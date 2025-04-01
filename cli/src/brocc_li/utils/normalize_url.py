def normalize_url(url: str) -> str | None:
    """Normalize URLs to a canonical form.

    - Removes trailing slashes
    - Removes protocol (http/https)
    - Removes www.
    - Lowercases the domain
    - Preserves path case (as it may be significant)
    - Returns None if protocol is invalid (not http/https/file)
    - Normalizes file URLs to use correct path format for the platform
    - Maintains URL encoding in file paths
    - Handles relative paths in file URLs
    - Preserves special characters in file paths
    - Supports Unix paths (home directories, device files, etc.)
    - Supports macOS specific paths (resource forks, app bundles, etc.)
    - Preserves Unicode characters in paths
    """
    import urllib.parse
    import os.path

    url = url.strip()

    # Validate and remove protocol
    if "://" in url:
        protocol, rest = url.split("://", 1)
        protocol = protocol.lower()

        # Handle file URLs specially
        if protocol == "file":
            # Parse and normalize the file path
            parsed = urllib.parse.urlparse(url)

            # Handle the case where netloc is used instead of path (file://path/to/file)
            file_path = parsed.path

            # Special handling for localhost - just ignore it
            if parsed.netloc and parsed.netloc.lower() == "localhost":
                # For localhost, don't add the netloc
                pass
            elif parsed.netloc:
                # If netloc exists and isn't localhost, prepend it to the path
                file_path = f"/{parsed.netloc}{file_path}"

            # Replace backslashes with forward slashes (for Windows paths)
            file_path = file_path.replace("\\", "/")

            # Normalize consecutive slashes while preserving leading slashes
            while "//" in file_path:
                file_path = file_path.replace("//", "/")

            # Special handling for root paths
            if file_path == "":
                return "file:///"

            # Convert to proper path for the current platform, preserving special paths
            # Don't normalize paths with special macOS components
            if "..namedfork" not in file_path:
                norm_path = os.path.normpath(file_path)
            else:
                norm_path = file_path

            # Ensure path uses forward slashes for URL format (even on Windows)
            path = norm_path.replace(os.path.sep, "/")

            # Make sure the path starts with a slash
            if not path.startswith("/"):
                path = "/" + path

            # Return normalized file URL
            return f"file://{path}"

        if protocol not in ("http", "https", "file"):
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
