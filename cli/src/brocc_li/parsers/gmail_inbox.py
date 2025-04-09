from typing import Any, Dict, List, Optional, cast

from bs4 import BeautifulSoup, Tag
from unstructured.documents.elements import Element, Table

from brocc_li.utils.logger import logger

# Noise patterns to filter UI elements
INBOX_NOISE_PATTERNS = [
    "Terms",
    "Privacy",
    "Advanced search",
    "Google apps",
    "Account Information",
    "Toggle",
    "refresh",
    "Refresh",
    "Sign out",
    "header",
    "loading",
]

# Message separator patterns
EMAIL_MARKER_PATTERNS = [
    r"---------- Forwarded message ---------",
    r"---------- Original message ----------",
    r"From:",
    r"Subject:",
    r"Date:",
    r"To:",
]


def _extract_email_metadata(text: str) -> Dict[str, str]:
    """Extract email metadata from text"""
    metadata = {
        "subject": "",
        "sender": "",
        "date": "",
    }

    lines = text.split("\n")
    for line in lines:
        if line.startswith("Subject:"):
            metadata["subject"] = line.replace("Subject:", "").strip()
        elif line.startswith("From:"):
            metadata["sender"] = line.replace("From:", "").strip()
        elif line.startswith("Date:"):
            metadata["date"] = line.replace("Date:", "").strip()

    return metadata


def _is_likely_email_table(element: Element) -> bool:
    """Check if a table element likely contains email content"""
    if not isinstance(element, Table):
        return False

    text = str(element).strip()
    # Email tables typically have decent content length
    if len(text) < 20:
        return False

    # Check for email markers
    for pattern in EMAIL_MARKER_PATTERNS:
        if pattern in text:
            return True

    # Check for common email content patterns
    if "wrote:" in text or "@" in text or "On " in text:
        return True

    return False


def _split_table_into_emails(table_text: str, debug: bool = False) -> List[Dict[str, Any]]:
    """Split table content into separate emails"""
    if debug:
        logger.debug(f"Parsing table content ({len(table_text)} chars)")

    emails = []
    lines = table_text.split("\n")

    # Find email separator indices
    separator_indices = [0]  # Start with first line
    for i, line in enumerate(lines):
        for pattern in EMAIL_MARKER_PATTERNS:
            if pattern in line and i > 0:  # Skip first line as it's already a separator
                if debug:
                    logger.debug(f"Found email separator at line {i}: {line[:50]}...")
                separator_indices.append(i)
                break

    # Add end index
    separator_indices.append(len(lines))

    # Process each potential email chunk
    for i in range(len(separator_indices) - 1):
        start_idx = separator_indices[i]
        end_idx = separator_indices[i + 1]

        # Get email chunk
        email_lines = lines[start_idx:end_idx]
        if not email_lines:
            continue

        email_text = "\n".join(email_lines)

        # Extract metadata
        metadata = _extract_email_metadata(email_text)

        # If no subject found, try to find one from the text
        if not metadata["subject"]:
            # Look for a reasonable subject line
            for line in email_lines:
                # Skip empty or very short lines
                if len(line) < 5:
                    continue
                # Skip lines that are just email headers
                if any(marker in line for marker in ["From:", "To:", "Date:"]):
                    continue
                # Use this as a subject if it's reasonable length
                if 5 < len(line) < 200:
                    metadata["subject"] = line
                    break

        # Last resort default subject
        if not metadata["subject"]:
            metadata["subject"] = f"Email {i + 1}"

        # Add the email
        emails.append(
            {
                "subject": metadata["subject"],
                "sender": metadata["sender"],
                "date": metadata["date"],
                "content": email_text,
            }
        )

        if debug:
            logger.debug(f"Extracted email {i + 1}: {metadata['subject'][:50]}...")

    # If no emails were extracted (no separators found), treat the whole table as one email
    if not emails:
        if debug:
            logger.debug("No separators found, treating entire table as one email")

        metadata = _extract_email_metadata(table_text)

        # Find a suitable subject
        subject = metadata["subject"]
        if not subject:
            for line in lines:
                if len(line) > 5 and len(line) < 200:
                    subject = line
                    break

        if not subject:
            subject = "Email"

        emails.append(
            {
                "subject": subject,
                "sender": metadata["sender"],
                "date": metadata["date"],
                "content": table_text,
            }
        )

    return emails


def _extract_email_details(
    email_element: Tag, debug: bool = False
) -> Optional[Dict[str, Optional[str]]]:
    """Extract details (sender, subject, date, preview) from an email element (usually a <tr>)."""
    details: Dict[str, Optional[str]] = {
        "sender": None,
        "subject": None,
        "date": None,
        "preview": None,
    }

    try:
        # --- Selectors based on typical Gmail HTML structure (td:nth-of-type is 1-based) ---
        sender_cell = email_element.select_one("td:nth-of-type(4)")
        subject_cell = email_element.select_one("td:nth-of-type(5)")
        date_cell = email_element.select_one("td:nth-of-type(6)")

        # --- Sender Extraction (from 4th cell) ---
        if sender_cell:
            sender_span = sender_cell.select_one("span[email]")
            if sender_span:
                details["sender"] = sender_span.get_text(strip=True)
            else:
                # Fallback: Look for span with name attribute
                name_span = sender_cell.select_one("span[name]")
                if name_span:
                    details["sender"] = name_span.get_text(strip=True)
                else:
                    # Last resort: take all text from sender cell
                    details["sender"] = sender_cell.get_text(strip=True)

        # --- Date Extraction (from 6th cell) ---
        if date_cell:
            date_span = date_cell.select_one("span[title]")
            if date_span:
                date_title = date_span.get("title")
                if isinstance(date_title, str):
                    details["date"] = date_title
                elif isinstance(date_title, list):
                    details["date"] = str(date_title[0]) if date_title else None
            else:
                details["date"] = date_cell.get_text(strip=True)

        # --- Subject and Preview Extraction (from 5th cell) ---
        subject_parts = []
        preview_parts = []
        if subject_cell:
            # Try to find distinct subject spans (e.g., bold, specific classes)
            # This part is highly heuristic and might need tuning!
            potential_subject_spans = subject_cell.select(
                "span.bog span[alt], b, span.bqe"
            )  # Examples
            if potential_subject_spans:
                subject_parts = [
                    s.get_text(strip=True)
                    for s in potential_subject_spans
                    if s.get_text(strip=True)
                ]
            else:
                # Fallback: Use first few significant spans as subject guess
                all_spans = subject_cell.find_all("span", recursive=False)  # Direct children spans
                span_texts = [s.get_text(strip=True) for s in all_spans if s.get_text(strip=True)]
                if span_texts:
                    subject_parts.append(span_texts[0])  # Take the first one

            # Combine subject parts
            details["subject"] = " ".join(subject_parts).strip(" -\t\n\r")
            if not details["subject"]:
                # Last resort if subject parts are empty but cell has text
                subject_cell_text = subject_cell.get_text(strip=True)
                if subject_cell_text and subject_cell_text != details["sender"]:
                    details["subject"] = subject_cell_text.split("-")[
                        0
                    ].strip()  # Guess based on first part

            # Preview: Look for dimmer text spans (e.g., class y2) or text after subject
            preview_spans = subject_cell.select("span.y2")  # Common class for preview text
            if preview_spans:
                preview_parts = [
                    s.get_text(strip=True) for s in preview_spans if s.get_text(strip=True)
                ]
                details["preview"] = " ".join(preview_parts).strip(" -\t\n\r")
            else:
                # Fallback: Try to get text after subject parts within the cell
                all_cell_text = subject_cell.get_text(" ", strip=True)
                current_subject = details.get("subject")
                if current_subject and current_subject in all_cell_text:
                    candidate = all_cell_text.split(current_subject, 1)[-1].strip(" -\t\n\r")
                    if candidate and len(candidate) > 3:
                        details["preview"] = candidate[:150]

        # Clean up extracted text slightly
        if details["sender"]:
            details["sender"] = details["sender"].strip("\t\n\r .:")
        if details["subject"]:
            details["subject"] = details["subject"].strip("\t\n\r .:")
        if details["preview"]:
            details["preview"] = details["preview"].strip("\t\n\r .:")

        if debug:
            sender_val = details.get("sender", "None")
            subject_val = details.get("subject", "None")
            date_val = details.get("date", "None")
            preview_raw = details.get("preview")
            preview_safe = preview_raw if preview_raw is not None else ""
            preview_val = preview_safe[:50]
            logger.debug(
                f"Extracted details: Sender='{sender_val}', Subject='{subject_val}', Date='{date_val}', Preview='{preview_val}...'"
            )

        # Return None if essential info is missing (sender or subject)
        if not details["sender"] and not details["subject"]:
            if debug:
                logger.debug("Missing essential sender/subject, discarding element.")
            return None

        # If only sender found, use sender as subject
        if details["sender"] and not details["subject"]:
            details["subject"] = details["sender"]
            if debug:
                logger.debug("Using sender as subject as fallback.")

        return details

    except Exception as e:
        if debug:
            logger.error(f"Error extracting details: {e}")
        return None


def gmail_inbox_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Parses the HTML content of Gmail inbox into Markdown using BeautifulSoup.
    Focuses on finding email rows/items based on common Gmail structures.
    """
    logger.info("Starting Gmail Inbox HTML processing with BeautifulSoup...")
    try:
        soup = BeautifulSoup(html, "html.parser")

        if debug:
            title = soup.title.text if soup.title else "No title found"
            logger.debug(f"Page title: '{title}'")
            logger.debug("First 5 tables:")
            for i, table_element in enumerate(soup.find_all("table", limit=5)):
                if isinstance(table_element, Tag):
                    table = cast(Tag, table_element)
                    table_id = table.get("id", "no-id")
                    table_class = table.get("class", "no-class")
                    logger.debug(
                        f"  Table {i}: id='{table_id}', class='{table_class}', text_preview='{table.get_text(strip=True)[:50]}...'"
                    )
                else:
                    logger.debug(
                        f"  Table {i}: Not a Tag element (type: {type(table_element).__name__})"
                    )
            logger.debug("First 5 divs:")
            for i, div_element in enumerate(soup.find_all("div", limit=5)):
                if isinstance(div_element, Tag):
                    div = cast(Tag, div_element)
                    div_id = div.get("id", "no-id")
                    div_class = div.get("class", "no-class")
                    logger.debug(
                        f"  Div {i}: id='{div_id}', class='{div_class}', text_preview='{div.get_text(strip=True)[:50]}...'"
                    )
                else:
                    logger.debug(
                        f"  Div {i}: Not a Tag element (type: {type(div_element).__name__})"
                    )

        # --- Find Email Container(s) ---
        # Attempt 1: Look for the main table often used by Gmail (heuristic)
        email_container: Optional[Tag] = None
        potential_tables = soup.select('table[role="grid"]')
        if debug:
            logger.debug(f"Found {len(potential_tables)} tables with role='grid'")
        if potential_tables:
            valid_tables = [t for t in potential_tables if isinstance(t, Tag)]
            if valid_tables:
                email_container = max(valid_tables, key=lambda t: len(str(t)))
                if debug and email_container:
                    container_id = email_container.get("id", "no-id")
                    container_class = email_container.get("class", "no-class")
                    logger.debug(
                        f"Selected table container: id='{container_id}', class='{container_class}', size={len(str(email_container))}"
                    )
        if not email_container:
            # Attempt 2: Fallback to looking for divs with specific jscontroller/jsaction
            potential_divs = soup.select("div[jscontroller][jsaction]")
            if debug:
                logger.debug(
                    f"No grid tables found. Found {len(potential_divs)} divs with jscontroller/jsaction."
                )
            if potential_divs:
                valid_divs = [d for d in potential_divs if isinstance(d, Tag)]
                if valid_divs:
                    email_container = max(valid_divs, key=lambda d: len(str(d)))
                    if debug and email_container:
                        container_id = email_container.get("id", "no-id")
                        container_class = email_container.get("class", "no-class")
                        logger.debug(
                            f"Selected div container: id='{container_id}', class='{container_class}', size={len(str(email_container))}"
                        )
        if not email_container:
            logger.warning("Could not find a likely email container element.")
            # Attempt 3: Last resort - use the whole body (might be very noisy)
            email_container = soup.body
            if not email_container:
                logger.error("HTML body not found.")
                return "<!-- Error: HTML body not found -->"
            if debug:
                logger.debug("Using entire HTML body as container (last resort).")

        # --- Find Individual Email Elements ---
        email_elements = []
        if email_container and isinstance(email_container, Tag):
            # Attempt 1: Look for table rows within the container
            email_elements = email_container.select('tr[role="row"]')
            if debug:
                logger.debug(
                    f"Found {len(email_elements)} table rows with role='row' within the container."
                )

            if not email_elements:
                # Attempt 2: Fallback to divs with specific data attributes (less common)
                email_elements = email_container.select("div[data-message-id]")  # Example attribute
                if debug:
                    logger.debug(
                        f"No table rows found. Found {len(email_elements)} divs with 'data-message-id'."
                    )

        all_emails: List[Dict[str, Optional[str]]] = []
        if not email_elements:
            logger.warning("Could not find individual email elements within the container.")
            # Fallback: Maybe the container itself has the email text?
            if email_container and isinstance(email_container, Tag):
                container_text = email_container.get_text(strip=True)
                if len(container_text) > 50:  # Only if there's substantial text
                    logger.warning("Using container's text as a single email block.")
                    # Create a placeholder structure
                    all_emails = [
                        {
                            "sender": "Unknown",
                            "subject": "Inbox Content",
                            "date": "Unknown",
                            "preview": container_text[:500],  # Limit length
                        }
                    ]
        else:
            # --- Process Each Email Element ---
            if debug:
                logger.debug(f"Processing {len(email_elements)} potential email elements...")
            for i, element in enumerate(email_elements):
                # Ensure element is a Tag before processing
                if not isinstance(element, Tag):
                    if debug:
                        logger.debug(
                            f"Skipping element {i + 1} because it is not a Tag (type: {type(element).__name__})"
                        )
                    continue

                if debug:
                    element_text = element.get_text(strip=True)
                    logger.debug(
                        f"Processing element {i + 1}: tag={element.name}, preview='{element_text[:60]}...'"
                    )

                # Cast element to Tag for type checker reassurance
                details = _extract_email_details(cast(Tag, element), debug=debug)
                if details:
                    all_emails.append(details)
                elif debug:
                    logger.debug(
                        f"Skipping element {i + 1} due to missing details or extraction error."
                    )

        # --- Convert to Markdown (Updated Formatting) ---
        if not all_emails:
            logger.warning("No emails extracted after processing elements.")
            return "<!-- No emails found in the inbox -->"

        markdown_parts = ["# Gmail Inbox\n"]
        for email in all_emails:
            # Use subject (or sender fallback) as header, no "Email N:" prefix
            subject = email.get("subject") or email.get("sender") or "Email"
            markdown_parts.append(f"## {subject}")

            # Add sender and date if available
            sender = email.get("sender")
            if sender:
                markdown_parts.append(f"**From:** {sender}")
            date = email.get("date")
            if date:
                markdown_parts.append(f"**Date:** {date}")

            # Add preview as blockquote
            preview = email.get("preview")
            if preview:
                markdown_parts.append("\n> " + preview.replace("\n", "\n> "))

            # No "---" separator added here

        # Join with double newlines
        result_md = "\n\n".join(markdown_parts)
        logger.info(f"Successfully processed Gmail Inbox HTML. Found {len(all_emails)} emails.")
        if debug:
            logger.debug(f"Final markdown contains {len(result_md.splitlines())} lines")

        return result_md.strip()

    except Exception as e:
        logger.error(f"Error processing Gmail Inbox HTML with BeautifulSoup: {e}")
        return f"Error processing Gmail Inbox HTML: {e}"
