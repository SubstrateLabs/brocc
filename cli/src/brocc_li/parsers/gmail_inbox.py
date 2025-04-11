from typing import Dict, List, Optional

from bs4 import BeautifulSoup, Tag
from rich.markup import escape

from brocc_li.parsers.soup_utils import (
    extract_date_from_element,
    find_largest_container,
)
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
        # These might need adjustment based on exact HTML variations
        sender_cell = email_element.select_one(
            "td:nth-of-type(4) span[email], td:nth-of-type(4) span[name]"
        )
        if not sender_cell:
            sender_cell = email_element.select_one("td:nth-of-type(4)")  # Fallback to whole cell
        subject_cell = email_element.select_one("td:nth-of-type(5)")
        date_cell = email_element.select_one("td:nth-of-type(6)")

        # --- Sender Extraction ---
        if sender_cell:
            details["sender"] = sender_cell.get_text(strip=True)

        # --- Date Extraction (Using our new utility function) ---
        if date_cell:
            details["date"] = extract_date_from_element(date_cell, debug=debug)

        # --- Subject and Preview Extraction ---
        if subject_cell:
            # Strategy: Find the most prominent text first (often bold or specific spans)
            # Combine text from spans that seem part of the subject line
            subject_parts = []
            preview_text = None

            # Select potential subject elements (adjust selectors as needed)
            # This includes bold tags, specific spans Gmail uses
            potential_subject_elements = subject_cell.select("b, span.bqe, span.bog span[alt]")
            if potential_subject_elements:
                subject_parts = [
                    el.get_text(strip=True)
                    for el in potential_subject_elements
                    if el.get_text(strip=True)
                ]

            # Get the full text of the cell for finding preview
            full_cell_text = subject_cell.get_text(" ", strip=True)

            # If parts were found, combine them
            guessed_subject = " ".join(subject_parts).strip()

            # If no specific elements found, try using the start of the cell text
            if not guessed_subject and full_cell_text:
                # Take the first significant part before a common separator like " - "
                guessed_subject = full_cell_text.split(" - ")[0].strip()
                # Avoid using sender name as subject if it repeats
                if guessed_subject == details["sender"]:
                    guessed_subject = full_cell_text  # Use full text if first part is just sender

            details["subject"] = guessed_subject if guessed_subject else None

            # Extract Preview: Text that isn't part of the determined subject
            current_subject = details.get("subject")
            if full_cell_text and current_subject:
                # Look for specific preview spans first
                preview_span = subject_cell.select_one("span.y2")
                if preview_span:
                    preview_text = preview_span.get_text(" ", strip=True)
                else:
                    # Fallback: try text after the subject in the cell
                    try:
                        subject_index = full_cell_text.index(current_subject)
                        potential_preview = full_cell_text[
                            subject_index + len(current_subject) :
                        ].strip(" -\t\n\r")
                        if (
                            potential_preview and len(potential_preview) > 5
                        ):  # Basic check for meaningful preview
                            preview_text = potential_preview
                    except ValueError:
                        # If subject wasn't found exactly (e.g. due to stripping), take text after first few words
                        if len(full_cell_text.split()) > 3:  # Heuristic
                            preview_text = " ".join(full_cell_text.split()[3:])[
                                :150
                            ]  # Limit length

            details["preview"] = preview_text.strip(" -\t\n\r") if preview_text else None

        # --- Final Cleanup --- #
        if details["sender"]:
            # Remove common Gmail UI prefixes from sender
            prefixes_to_remove = [
                "Click to teach Substrate Labs Mail this conversation is important",
                "Click to teach Substrate Labs Mail this conversation is not important",
                "Important mainly because it was sent directly to you.",
                "Important because previous messages in the conversation were important.",
                "Important according to Google magic.",
            ]
            cleaned_sender = details["sender"]
            for prefix in prefixes_to_remove:
                if cleaned_sender.startswith(prefix):
                    # Attempt to extract actual sender name after the prefix
                    remainder = cleaned_sender[len(prefix) :].strip(" .-")
                    # Simple heuristic: if remainder is short and capitalized, likely the name
                    if remainder and len(remainder) < 50 and any(c.isupper() for c in remainder):
                        cleaned_sender = remainder
                        break  # Stop after first match
                    else:
                        # If remainder doesn't look like a name, maybe it's just the prefix
                        # Keep the original or decide on a better fallback? For now, keep original if unsure.
                        pass  # Stick with original sender text for now
            details["sender"] = cleaned_sender.strip("\t\n\r .:")

        current_subject = details.get("subject")
        if current_subject:
            details["subject"] = current_subject.strip("\t\n\r .:")
            # Remove common prefixes often mistakenly included
            if details["subject"] and details["subject"].startswith("todo"):
                details["subject"] = details["subject"][4:].strip()

        current_preview = details.get("preview")
        if current_preview:
            details["preview"] = current_preview.strip("\t\n\r .:")
            # Truncate long previews
            # Ensure preview is not None before checking length
            current_preview_str = details["preview"]
            # Separate checks for clarity and potentially for the type checker
            if current_preview_str is not None:
                if len(current_preview_str) > 200:
                    details["preview"] = current_preview_str[:200] + "..."

        if details["date"]:
            details["date"] = details["date"].strip("\t\n\r .:")

        if debug:
            sender_val = escape(str(details.get("sender", "None")))
            subject_val = escape(str(details.get("subject", "None")))
            date_val = escape(str(details.get("date", "None")))
            # Fix the first linter error by ensuring preview_safe is always a string
            preview_safe = details.get("preview", "") or ""  # Double protection
            # Now slice it safely and escape
            preview_val = escape(preview_safe[:50])
            logger.debug(
                f"Extracted details: Sender='{sender_val}', Subject='{subject_val}', Date='{date_val}', Preview='{preview_val}...'"
            )

        # Return None if essential info is missing (sender or subject)
        if not details["sender"] and not details["subject"]:
            if debug:
                logger.debug("Missing essential sender/subject, discarding element.")
            return None

        # Handle cases where subject might be missing or same as sender
        current_subject = details.get("subject")  # Re-fetch potentially updated subject
        current_sender = details.get("sender")
        current_preview = details.get("preview")

        if not current_subject or current_subject == current_sender:
            # If preview exists and is not None/empty, use that as subject maybe?
            # Separate checks for clarity and potentially for the type checker
            preview_is_valid = False
            if current_preview is not None:
                if len(current_preview) > 5:
                    preview_is_valid = True

            if (
                preview_is_valid and current_preview is not None
            ):  # Check current_preview is not None again for type checker
                details["subject"] = current_preview.split(".")[0][
                    :80
                ]  # Take first sentence of preview
            elif current_sender:
                details["subject"] = f"Email from {current_sender}"
            else:
                details["subject"] = "Email"
            if debug:
                safe_subject = escape(str(details["subject"]))
                logger.debug(
                    f"Subject missing or same as sender, fallback subject: '{safe_subject}'"
                )

        return details

    except Exception as e:
        if debug:
            error_msg = escape(str(e))
            logger.error(f"Error extracting details: {error_msg}")
        return None


def gmail_inbox_html_to_md(html: str, debug: bool = False) -> Optional[str]:
    """
    Parses the HTML content of Gmail inbox into Markdown using BeautifulSoup ONLY.
    Focuses on finding email rows/items based on common Gmail structures.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")

        if debug:
            title = escape(soup.title.text if soup.title else "No title found")
            logger.debug(f"Page title: '{title}'")
            # Log first few tables/divs for structure inspection
            logger.debug("Sample table structure:")
            for i, table in enumerate(soup.find_all("table", limit=3)):
                safe_preview = escape(str(table)[:100])
                logger.debug(f" Table {i}: {safe_preview}...")
            logger.debug("Sample div structure:")
            for i, div in enumerate(soup.find_all("div", limit=3)):
                safe_preview = escape(str(div)[:100])
                logger.debug(f" Div {i}: {safe_preview}...")

        # --- Find Email Container using our new utility function ---
        email_container = find_largest_container(
            soup,
            'table[role="grid"]',
            fallbacks=["div[jscontroller][jsaction]", 'table:has(tr[role="row"])'],
            debug=debug,
        )

        if not email_container:
            logger.warning(
                "Could not find a likely email container element. Using body as fallback."
            )
            email_container = soup.body
            if not email_container:
                logger.error("HTML body not found.")
                return "<!-- Error: HTML body not found -->"

        # --- Find Individual Email Elements (Rows) --- #
        email_elements: List[Tag] = []
        if email_container and isinstance(email_container, Tag):
            # Primary target: Table rows with role='row' within the container
            email_elements = email_container.select('tr[role="row"]')
            if not email_elements:
                # Fallback: Look for divs that might represent emails (less common)
                # Example: divs with a specific data attribute or class pattern
                email_elements = email_container.select(
                    "div[data-message-id]"
                )  # Adjust selector if needed
                if debug and email_elements:
                    logger.debug(f"Found {len(email_elements)} potential email divs as fallback.")

        if not email_elements:
            logger.warning(
                "Could not find individual email elements (e.g., <tr> with role='row') within the container."
            )
            # Attempt to extract content directly from container if no rows found
            container_text = email_container.get_text(strip=True)
            if len(container_text) > 50:
                logger.warning("Using container's text as a single block (fallback).")
                # Basic markdown structure for the whole block
                title_text = soup.title.text if soup.title else "Inbox Content"
                subject = title_text[:80]  # Truncate title if needed
                return f"# {subject}\n\n{container_text[:1000]}..."  # Limit length
            else:
                return "<!-- No emails or significant content found -->"

        # --- Process Each Email Element --- #
        all_emails: List[Dict[str, Optional[str]]] = []
        if debug:
            logger.debug(f"Processing {len(email_elements)} potential email elements...")

        processed_count = 0
        for i, element in enumerate(email_elements):
            if not isinstance(element, Tag):
                if debug:
                    logger.debug(f"Skipping element {i + 1} (not a Tag)")
                continue

            if debug:
                element_text = escape(element.get_text(strip=True))
                logger.debug(
                    f" Processing element {i + 1}/{len(email_elements)}: <{element.name}> preview='{element_text[:60]}...'"
                )

            details = _extract_email_details(element, debug=debug)
            if details:
                # Basic check to avoid adding clearly non-email rows (e.g. headers/footers)
                if details.get("sender") or details.get("subject") or details.get("date"):
                    all_emails.append(details)
                    processed_count += 1
                elif debug:
                    logger.debug(
                        f" Skipping element {i + 1} - details extracted but seemed empty/invalid."
                    )
            elif debug:
                logger.debug(f" Skipping element {i + 1} - failed to extract details.")

        # --- Convert to Markdown --- #
        if not all_emails:
            logger.warning(
                f"No valid emails extracted after processing {len(email_elements)} elements."
            )
            return "<!-- No emails found in the inbox -->"

        logger.info(
            f"Extracted details for {processed_count} emails from {len(email_elements)} elements."
        )

        markdown_parts = ["# Gmail Inbox\n"]
        for email in all_emails:
            # Fix the 2nd and 3rd linter errors with explicit type handling
            subject = email.get("subject", "Email") or "Email"  # Ensure not None

            # Now we can safely slice and check length
            clean_subject = subject[:80]
            if len(subject) > 80:  # This is safe now
                clean_subject += "..."

            markdown_parts.append(f"## {clean_subject}")

            sender = email.get("sender")
            if sender:
                markdown_parts.append(f"**From:** {sender}")

            date = email.get("date")
            if date:
                markdown_parts.append(
                    f"**Date:** {date}"
                )  # Date is already cleaned in _extract_email_details

            preview = email.get("preview")
            if preview:
                # Format preview as a blockquote
                # Ensure preview is a string before replacing
                safe_preview = preview if isinstance(preview, str) else str(preview)
                markdown_parts.append("\n> " + safe_preview.replace("\n", "\n> "))

        result_md = "\n\n".join(markdown_parts)

        logger.info(f"Found {len(all_emails)} Gmail emails.")
        if debug:
            logger.debug(f"Final markdown contains {len(result_md.splitlines())} lines")

        return result_md.strip()

    except Exception as e:
        # Fix logger error - escape any potential Rich markup in error message
        error_msg = escape(str(e))
        logger.error(f"Critical error processing Gmail Inbox HTML with BeautifulSoup: {error_msg}")
        # Optionally add the traceback as a separate string if needed
        import traceback

        logger.debug(f"Traceback: {escape(traceback.format_exc())}")
        return f"Error processing Gmail Inbox HTML: {error_msg}"
