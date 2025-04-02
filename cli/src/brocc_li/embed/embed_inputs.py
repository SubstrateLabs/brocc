from brocc_li.types.doc import Doc


def embed_header(doc: Doc) -> str:
    """Create a formatted header string with relevant metadata from a Doc."""
    components = []

    # Add title if available
    if doc.title:
        components.append(f"Title: {doc.title}")

    # Add description if available
    if doc.description:
        components.append(f"Description: {doc.description}")

    # Add source information
    components.append(f"Source: {doc.source.value}")
    components.append(f"Source Type: {doc.source_type.value}")

    # Add URL if available
    if doc.url:
        components.append(f"URL: {doc.url}")

    # Add contact information if available
    if doc.contact_name:
        components.append(f"Contact: {doc.contact_name}")

    if doc.contact_identifier:
        components.append(f"Contact ID: {doc.contact_identifier}")

    # Add participant information if available
    if doc.participant_names:
        components.append(f"Participants: {', '.join(doc.participant_names)}")

    # Add source location name if available
    if doc.source_location_name:
        components.append(f"Source Location: {doc.source_location_name}")

    # Add keywords if available
    if doc.keywords:
        components.append(f"Keywords: {', '.join(doc.keywords)}")

    # Add metadata if available
    if doc.metadata:
        # Format metadata as key-value pairs
        metadata_str = ", ".join(f"{k}: {v}" for k, v in doc.metadata.items())
        components.append(f"Metadata: {metadata_str}")

    # Join with newlines
    return "\n".join(components)
