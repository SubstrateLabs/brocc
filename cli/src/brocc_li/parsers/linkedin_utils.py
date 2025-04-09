import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import dateparser
from geotext import GeoText
from unstructured.documents.elements import Element, Image, NarrativeText, Text, Title

from brocc_li.utils.logger import logger

# List of noisy text patterns to filter out
NOISE_PATTERNS = [
    "Media player modal window",
    "Visit profile for",
    "Drop your files here",
    "Drag your files here",
    "Discover free and easy ways",
    "Hi Ben, are you hiring?",
    "Write article",
    "feed updates",
    "Visible to anyone on or off LinkedIn",
    "Media is loading",
    "Loaded:",
    "Stream Type LIVE",
    "Remaining time",
]

# Regex for playback speeds like 0.5x, 1x, 1.25x etc.
PLAYBACK_SPEED_REGEX = re.compile(r"^\d+(\.\d+)?x(,\s*selected)?$")
# Regex for timestamps like 0:56
TIMESTAMP_REGEX = re.compile(r"^\d+:\d{2}$")
# Regex for short time indicators like 23h, 1d, 2w (with optional space)
TIME_INDICATOR_REGEX = re.compile(r"^\d{1,2}\s?[hdwmy]$")

# Common patterns used across multiple functions
COMMON_ROLE_PATTERNS = {
    "leadership": [
        "founder",
        "co-founder",
        "ceo",
        "cto",
        "coo",
        "cfo",
        "chief",
        "president",
        "vice president",
        "vp",
        "executive",
        "director",
        "head",
        "lead",
        "principal",
        "manager",
        "chair",
        "chairman",
        "chairwoman",
        "chairperson",
        "board member",
    ],
    "technical": [
        "engineer",
        "developer",
        "programmer",
        "architect",
        "administrator",
        "devops",
        "sre",
        "reliability",
        "security",
        "data scientist",
        "ml engineer",
        "ai",
        "backend",
        "frontend",
        "full-stack",
        "fullstack",
        "mobile",
        "web",
        "cloud",
        "infrastructure",
        "network",
        "systems",
        "qa",
        "quality",
        "test",
        "testing",
        "database",
        "dba",
        "analytics",
        "analyst",
        "research",
        "scientist",
    ],
    "business": [
        "product",
        "project",
        "program",
        "marketing",
        "growth",
        "sales",
        "account",
        "customer success",
        "operations",
        "hr",
        "human resources",
        "talent",
        "recruiter",
        "recruiting",
        "business development",
        "partnerships",
        "strategy",
        "consultant",
        "advisor",
        "finance",
        "financial",
        "accounting",
        "legal",
        "compliance",
        "design",
        "ux",
        "ui",
        "content",
        "communication",
    ],
    "seniority": [
        "senior",
        "sr",
        "junior",
        "jr",
        "staff",
        "principal",
        "associate",
        "intern",
        "apprentice",
        "fellow",
        "lead",
        "head of",
        "chief",
        "executive",
        "director",
    ],
}

RELATIONSHIP_INDICATORS = [
    " at ",
    "@",
    " in ",
    " with ",
    " for ",
    "•",
    " of ",
    "|",
    "→",
    " - ",
    "&",
    "and",
    "working on",
    "specializing in",
]

CONNECTION_PATTERNS = {
    "degree": ["connection", "degree", "2nd", "3rd", "1st"],
    "mutual": ["mutual", "shared", "common"],
    "phrases": [
        "are mutual",
        "is a mutual",
        "other mutual",
        "you both know",
        "you and",
        "both follow",
        "connected",
        "profile",
        "your network",
    ],
}

NON_NAME_INDICATORS = (
    [
        "@",
        "#",
        "http",
        ".com",
        "followers",
        "employees",
        "industry",
        "location",
        "linkedin",
        "website",
        "founded",
        "company",
        "page",
        "works at",
        "profile",
        "see all",
        "mountain view",
        "california",
        "ca",
        "san francisco",
        "new york",
        "success",
    ]
    + COMMON_ROLE_PATTERNS["leadership"]
    + COMMON_ROLE_PATTERNS["technical"]
    + COMMON_ROLE_PATTERNS["business"]
    + COMMON_ROLE_PATTERNS["seniority"]
)

LOCATION_INDICATORS = [
    "headquartered in",
    "based in",
    "located in",
    "location:",
    "offices in",
    "hq in",
    "hq:",
    "headquarters:",
    "main office:",
    "global hq",
    "regional hq",
    "primary location",
    "address:",
    # Common LinkedIn location prefixes
    "greater",
    "area of",
    "region of",
    # Common LinkedIn location suffixes
    "metropolitan area",
    "metro area",
    "bay area",
    "region",
    "district",
]

# Enhanced industry classifications based on LinkedIn's industry categories
INDUSTRY_CATEGORIES = [
    # Technology
    "software",
    "technology",
    "information technology",
    "computer",
    "internet",
    "saas",
    "cloud",
    "telecommunications",
    "tech",
    "artificial intelligence",
    "machine learning",
    "cybersecurity",
    "security",
    "networking",
    "electronics",
    "semiconductor",
    "hardware",
    "mobile",
    "app",
    "web",
    "enterprise",
    "data",
    "analytics",
    "big data",
    "it services",
    # Business Services
    "consulting",
    "management consulting",
    "services",
    "outsourcing",
    "staffing",
    "recruiting",
    "human resources",
    "hr",
    "business services",
    "professional services",
    "legal services",
    "legal",
    "accounting",
    "audit",
    "tax",
    "advisory",
    "market research",
    "research services",
    # Financial
    "finance",
    "financial",
    "banking",
    "investment",
    "wealth management",
    "venture capital",
    "private equity",
    "insurance",
    "fintech",
    "payments",
    "capital",
    "credit",
    "investment banking",
    # Healthcare
    "healthcare",
    "health",
    "medical",
    "hospital",
    "pharma",
    "pharmaceutical",
    "biotech",
    "biotechnology",
    "health tech",
    "life sciences",
    "clinical",
    "wellness",
    "patient care",
    "telemedicine",
    "digital health",
    "health insurance",
    # Media & Entertainment
    "media",
    "entertainment",
    "digital media",
    "publishing",
    "news",
    "broadcast",
    "film",
    "production",
    "music",
    "gaming",
    "games",
    "sports",
    "television",
    "advertising",
    "marketing",
    "creative",
    "design",
    "animation",
    "content",
    # Manufacturing & Industrial
    "manufacturing",
    "industrial",
    "construction",
    "engineering",
    "automotive",
    "aerospace",
    "defense",
    "chemical",
    "energy",
    "oil",
    "gas",
    "utilities",
    "mining",
    "materials",
    "machinery",
    "equipment",
    "electronics manufacturing",
    "textiles",
    "consumer goods",
    # Consumer
    "retail",
    "e-commerce",
    "ecommerce",
    "consumer",
    "food",
    "beverage",
    "restaurant",
    "hospitality",
    "hotel",
    "travel",
    "tourism",
    "luxury",
    "fashion",
    "apparel",
    "beauty",
    "cosmetics",
    "consumer electronics",
    "consumer services",
    "e-commerce",
    # Education
    "education",
    "edtech",
    "educational",
    "training",
    "learning",
    "academic",
    "school",
    "university",
    "college",
    "higher education",
    "professional development",
    "e-learning",
    # Non-profit & Government
    "nonprofit",
    "non-profit",
    "government",
    "public sector",
    "social services",
    "charity",
    "foundation",
    "ngo",
    "civic",
    "social enterprise",
    "community",
    "advocacy",
    # Transportation & Logistics
    "transportation",
    "logistics",
    "supply chain",
    "shipping",
    "freight",
    "aviation",
    "airline",
    "railway",
    "trucking",
    "delivery",
    "fleet management",
    "distribution",
    # Real Estate
    "real estate",
    "property",
    "commercial real estate",
    "residential",
    "housing",
    "leasing",
    "facilities",
    "construction",
    "architecture",
    "design",
    "development",
    # Agriculture
    "agriculture",
    "farming",
    "agtech",
    "food production",
    "forestry",
    "fishing",
    "livestock",
    "agribusiness",
]

# Comprehensive company types
COMPANY_TYPES = [
    # Standard business entities
    "public company",
    "private company",
    "privately held",
    "public limited company",
    "plc",
    "private limited company",
    "ltd",
    "limited liability company",
    "llc",
    "corporation",
    "corp",
    "incorporated",
    "inc",
    "sole proprietorship",
    "partnership",
    "limited partnership",
    "lp",
    # Non-profit entities
    "nonprofit",
    "non-profit",
    "not-for-profit",
    "ngo",
    "non-governmental organization",
    "foundation",
    "charity",
    "501c3",
    "501(c)(3)",
    # Government & education
    "government",
    "government agency",
    "state-owned",
    "public sector",
    "university",
    "educational institution",
    "school",
    "academic institution",
    "research institution",
    # Other common entity types
    "startup",
    "self-employed",
    "freelance",
    "consultant",
    "joint venture",
    "cooperative",
    "co-op",
    "holding company",
    "subsidiary",
    "conglomerate",
    "group",
    "association",
    "trust",
    "social enterprise",
    "b-corp",
    "benefit corporation",
]


def is_noisy(element_text: str, debug: bool = False) -> bool:
    """Check if element text matches any known noise patterns."""
    text_strip = element_text.strip()
    text_lower = text_strip.lower()

    if not text_lower:
        if debug:
            logger.debug("Noisy check: empty text")
        return True

    # Specific check for standalone "Follow" button text
    if text_lower == "follow":
        if debug:
            logger.debug("Noisy check: matched exact text 'follow'")
        return True

    for pattern in NOISE_PATTERNS:
        # Use text_strip here for case-sensitive patterns if needed in future
        if pattern.lower() in text_lower:
            if debug:
                logger.debug(
                    f"Noisy check: matched pattern '{pattern}' in '{element_text[:50]}...'"
                )
            return True

    if PLAYBACK_SPEED_REGEX.match(text_lower):
        if debug:
            logger.debug(f"Noisy check: matched PLAYBACK_SPEED_REGEX: '{element_text}'")
        return True
    if TIMESTAMP_REGEX.match(text_lower):
        if debug:
            logger.debug(f"Noisy check: matched TIMESTAMP_REGEX: '{element_text}'")
        return True
    if TIME_INDICATOR_REGEX.match(text_lower):
        if debug:
            logger.debug(f"Noisy check: matched time indicator regex: '{element_text}'")
        return True

    if text_lower == "..." or text_lower.isdigit():
        if debug:
            logger.debug(f"Noisy check: matched '...' or isdigit: '{element_text}'")
        return True

    return False


def find_first_link(
    block_elements: List[Element], debug: bool = False
) -> Optional[Tuple[str, str, Element]]:
    """Find the first element with a likely profile/company link in its metadata."""
    for element in block_elements:
        metadata = getattr(element, "metadata", None)
        if not metadata:
            continue

        link_texts = getattr(metadata, "link_texts", None)
        link_urls = getattr(metadata, "link_urls", None)
        element_text = str(element).strip()

        if (
            link_texts
            and link_urls
            and isinstance(link_texts, list)
            and isinstance(link_urls, list)
        ):
            if link_texts[0] and link_urls[0]:  # Ensure they are not empty
                url = link_urls[0]
                text = link_texts[0].strip()

                # Prioritize profile/company links
                if "linkedin.com/in/" in url or "linkedin.com/company/" in url:
                    # Clean common noise from text
                    if text.endswith("'s profile photo"):
                        text = text[: -len("'s profile photo")]
                    elif text.endswith("'s profile photo"):
                        text = text[: -len("'s profile photo")]
                    text = (
                        text.replace("\u2022 1st", "")
                        .replace("\u2022 2nd", "")
                        .replace("\u2022 3rd+", "")
                        .strip()
                    )

                    # Attempt to deduplicate repeated names (e.g., "Name Name Title")
                    words = text.split()
                    if len(words) > 1 and words[0] == words[1]:
                        mid = len(text) // 2
                        first_half = text[:mid].strip()
                        second_half = text[mid:].strip()
                        if first_half == second_half:
                            text = first_half
                        # Consider element_text only if it *doesn't* contain the likely dirtier link_text
                        elif (
                            text not in element_text
                            and element_text.startswith(text)
                            and len(element_text) > len(text)
                        ):
                            text = element_text  # Less likely useful now?

                    # If cleaning results in empty text, skip
                    if not text:
                        continue

                    if debug:
                        logger.debug(f"Found profile link: {text} -> {url}")

                    return text.strip(), url, element  # Ensure final strip

    if debug:
        logger.debug("No suitable profile links found in block elements")

    return None


def check_block_type(block_elements: List[Element], debug: bool = False) -> Optional[str]:
    """Check if block text indicates a repost or comment."""
    for element in block_elements:
        if isinstance(element, (Text, NarrativeText)):
            text_lower = str(element).lower()
            if "reposted this" in text_lower:
                if debug:
                    logger.debug(f"Detected repost: '{str(element)[:50]}...'")
                return "(Repost)"
            if "commented on this" in text_lower:
                if debug:
                    logger.debug(f"Detected comment: '{str(element)[:50]}...'")
                return "(Comment)"

    if debug:
        logger.debug("No specific block type (repost/comment) detected")

    return None


def extract_company_metadata(
    elements: List[Element],
    max_elements: int = 15,
    include_end_idx: bool = False,
    debug: bool = False,
) -> Any:
    """
    Generic company metadata extraction from LinkedIn HTML elements.

    Args:
        elements: List of unstructured elements
        max_elements: Maximum number of elements to check for metadata (default: 15)
        include_end_idx: Whether to return the index where metadata ends (for posts)
        debug: Whether to output debug logs

    Returns:
        Dict with metadata or Tuple of (Dict, int) if include_end_idx is True
    """
    metadata: Dict[str, Optional[str]] = {
        "name": None,
        "description": None,
        "logo_url": None,
        "industry": None,
        "location": None,
        "website": None,
        "followers": None,
        "employees": None,
        "company_size": None,
        "type": None,
        "founded": None,
        "specialties": None,
    }

    # Typically, company info is among the first elements
    max_metadata_idx = min(max_elements, len(elements))
    end_idx = 0

    # Track all potential location texts for later geotext processing
    potential_locations = []

    for i, element in enumerate(elements[:max_metadata_idx]):
        text = str(element).strip()
        text_lower = text.lower()

        # Company name is likely a Title near the top
        if isinstance(element, Title) and not metadata["name"] and i < 3:
            metadata["name"] = text
            if debug:
                logger.debug(f"Found company name: {text}")

        # Logo is likely an Image with the company name in it
        elif isinstance(element, Image) and not metadata["logo_url"] and i < 3:
            if element.metadata and element.metadata.image_url:
                metadata["logo_url"] = element.metadata.image_url
                if debug:
                    logger.debug("Found company logo URL")

        # Description is usually a NarrativeText after the name/logo
        elif isinstance(element, NarrativeText) and not metadata["description"] and i < 10:
            if len(text) > 30:  # Likely a description if it's long enough
                metadata["description"] = text
                if debug:
                    logger.debug(f"Found company description: {text[:50]}...")

        # Website typically contains http/https or www
        elif (
            isinstance(element, Text)
            and not metadata["website"]
            and any(
                x in text_lower
                for x in ["http:", "https:", "www.", ".com", ".org", ".net", ".io", ".ai"]
            )
        ):
            # Clean up website text if it has a label
            website_text = text
            if "website" in text_lower:
                website_text = text.replace("Website", "").replace("website", "").strip()
            metadata["website"] = website_text
            if debug:
                logger.debug(f"Found website: {website_text}")

        # Industry and Location are typically short Text elements
        elif isinstance(element, Text):
            # Industry detection - improved with expanded list
            if not metadata["industry"]:
                # First check for explicitly labeled industry
                if "industry" in text_lower:
                    industry_text = (
                        text.replace("Industry", "").replace("industry", "").strip(".: ")
                    )
                    metadata["industry"] = industry_text
                    if debug:
                        logger.debug(f"Found labeled industry: {industry_text}")
                # Then check against our industry categories
                elif any(industry in text_lower for industry in INDUSTRY_CATEGORIES):
                    # If multiple industries match, use the full text as it might be a compound industry
                    if len([ind for ind in INDUSTRY_CATEGORIES if ind in text_lower]) > 1:
                        metadata["industry"] = text
                    else:
                        # Otherwise extract the matching industry as a substring
                        for industry in INDUSTRY_CATEGORIES:
                            if industry in text_lower:
                                start_idx = text_lower.find(industry)
                                # Get the industry and surrounding words
                                substring = text[
                                    max(0, start_idx - 5) : min(
                                        len(text), start_idx + len(industry) + 15
                                    )
                                ]
                                metadata["industry"] = substring.strip()
                                break
                    if debug:
                        logger.debug(f"Found industry: {metadata['industry']}")

            # Location detection - improved with geotext
            geo = GeoText(text)
            has_geo_entities = bool(geo.cities or geo.countries or geo.nationalities)
            is_potential_location = has_geo_entities or any(
                indicator.lower() in text_lower for indicator in LOCATION_INDICATORS
            )

            if is_potential_location:
                # Store with priority (1 = high, 2 = medium, 3 = low)
                priority = 3
                # Explicit location indicators get highest priority
                if any(indicator.lower() in text_lower for indicator in LOCATION_INDICATORS):
                    priority = 1
                # GeoText matches get medium-high priority
                elif has_geo_entities:
                    priority = 2
                # Store for later processing
                potential_locations.append((priority, text, geo))
                if debug:
                    entity_info = []
                    if geo.cities:
                        entity_info.append(f"cities: {geo.cities}")
                    if geo.countries:
                        entity_info.append(f"countries: {geo.countries}")
                    if geo.nationalities:
                        entity_info.append(f"nationalities: {geo.nationalities}")
                    if entity_info:
                        logger.debug(
                            f"Found potential location: {text} - GeoText entities: {', '.join(entity_info)}"
                        )
                    else:
                        logger.debug(f"Found potential location: {text} - pattern match")

            # Followers and employees count
            elif not metadata["followers"] and "followers" in text_lower:
                metadata["followers"] = text
                if debug:
                    logger.debug(f"Found followers: {text}")

            elif not metadata["employees"] and "employees" in text_lower:
                metadata["employees"] = text
                metadata["company_size"] = text  # Store as both for compatibility
                if debug:
                    logger.debug(f"Found employees: {text}")

            # Company type - improved detection
            elif not metadata["type"]:
                # Check for explicit type label
                if "type" in text_lower or "company type" in text_lower:
                    type_text = text
                    for label in ["Type:", "Type", "Company Type:", "Company Type"]:
                        type_text = type_text.replace(label, "").strip()
                    metadata["type"] = type_text
                    if debug:
                        logger.debug(f"Found labeled company type: {type_text}")
                # Check against comprehensive company types
                elif any(company_type in text_lower for company_type in COMPANY_TYPES):
                    # Extract the matching type
                    for company_type in COMPANY_TYPES:
                        if company_type in text_lower:
                            start_idx = text_lower.find(company_type)
                            end_idx = start_idx + len(company_type)
                            metadata["type"] = text[start_idx:end_idx]
                            break
                    if debug:
                        logger.debug(f"Found company type: {metadata['type']}")

            # Founded year - improved with dateparser
            elif not metadata["founded"]:
                # Look for founding date patterns
                founded_indicators = [
                    "founded",
                    "established",
                    "est.",
                    "started",
                    "launched",
                    "created",
                    "inception",
                    "since",
                    "founded in",
                    "established in",
                    "est. in",
                ]
                if any(indicator in text_lower for indicator in founded_indicators):
                    # First try with dateparser
                    parsed_date = None

                    # Try to extract just the year portion if possible
                    year_pattern = re.compile(r"\b(19\d{2}|20[0-2]\d)\b")
                    year_matches = year_pattern.findall(text)

                    if year_matches:
                        # Use the first year found
                        metadata["founded"] = year_matches[0]
                        if debug:
                            logger.debug(f"Found founding year: {metadata['founded']} from pattern")
                    else:
                        # Try with dateparser for more complex cases
                        try:
                            # Remove common label text to help dateparser
                            for label in founded_indicators:
                                if label in text_lower:
                                    clean_text = text.lower().replace(label, "").strip()
                                    parsed_date = dateparser.parse(clean_text)
                                    if parsed_date:
                                        break

                            # If no date found, try the full text as a fallback
                            if not parsed_date:
                                parsed_date = dateparser.parse(text)

                            if parsed_date:
                                # Extract just the year from the parsed date
                                year = parsed_date.year
                                if 1800 <= year <= datetime.now().year:
                                    metadata["founded"] = str(year)
                                    if debug:
                                        logger.debug(
                                            f"Found founding year: {metadata['founded']} from dateparser"
                                        )
                                else:
                                    # Fallback to the original text if year is unreasonable
                                    founded_text = text
                                    for label in founded_indicators:
                                        founded_text = founded_text.replace(label, "").strip()
                                    metadata["founded"] = founded_text
                                    if debug:
                                        logger.debug(
                                            f"Found founded text (invalid year): {metadata['founded']}"
                                        )
                            else:
                                # If dateparser fails, fall back to the original text
                                founded_text = text
                                for label in founded_indicators:
                                    founded_text = founded_text.replace(label, "").strip()
                                metadata["founded"] = founded_text
                                if debug:
                                    logger.debug(
                                        f"Found founded text (no date): {metadata['founded']}"
                                    )
                        except Exception as e:
                            # Handle any dateparser errors gracefully
                            if debug:
                                logger.debug(f"Error parsing date from '{text}': {e}")
                            # Fallback to just the text with labels removed
                            founded_text = text
                            for label in founded_indicators:
                                founded_text = founded_text.replace(label, "").strip()
                            metadata["founded"] = founded_text
                elif re.match(r"^(19\d{2}|20[0-2]\d)$", text.strip()):
                    # Just year detection
                    metadata["founded"] = text.strip()
                    if debug:
                        logger.debug(f"Found potential founding year: {text}")

            # Specialties
            elif not metadata["specialties"] and (
                "specialties" in text_lower
                or "specializations" in text_lower
                or "focus areas" in text_lower
            ):
                specialties_text = text
                for label in [
                    "Specialties:",
                    "Specialties",
                    "Specializations:",
                    "Specializations",
                    "Focus Areas:",
                    "Focus Areas",
                ]:
                    specialties_text = specialties_text.replace(label, "").strip()
                metadata["specialties"] = specialties_text
                if debug:
                    logger.debug(f"Found specialties: {metadata['specialties']}")

        # Stop when we find a post title (for company posts page)
        if (
            include_end_idx
            and isinstance(element, Title)
            and ("Feed post" in text or "Activity" in text)
        ):
            end_idx = i
            if debug:
                logger.debug(f"Stopping metadata extraction at element {i}: {text}")
            break

    # Process the collected location data with geotext
    if potential_locations and not metadata["location"]:
        # Sort by priority (1 = highest)
        potential_locations.sort(key=lambda x: x[0])

        for priority, location_text, geo in potential_locations:
            # For high priority (explicit location) items, use them directly
            if priority == 1:
                metadata["location"] = location_text
                if debug:
                    logger.debug(f"Setting location from explicit indicator: {location_text}")
                break

            # For others, check if GeoText found entities
            if geo.cities or geo.countries:
                if geo.cities and geo.countries:
                    # Both city and country - use the original text as it's likely well-formatted
                    metadata["location"] = location_text
                    if debug:
                        logger.debug(
                            f"Setting location with both city and country: {location_text}"
                        )
                    break
                elif geo.cities:
                    # Just cities
                    if len(geo.cities) == 1:
                        # Single city - we can be confident
                        metadata["location"] = location_text
                        if debug:
                            logger.debug(f"Setting location with single city: {location_text}")
                        break
                    else:
                        # Multiple cities - might be less reliable, but still useful
                        metadata["location"] = location_text
                        if debug:
                            logger.debug(f"Setting location with multiple cities: {location_text}")
                        break
                elif geo.countries:
                    # Just countries
                    metadata["location"] = location_text
                    if debug:
                        logger.debug(f"Setting location with country: {location_text}")
                    break

        # If still no location but we have candidates, use the highest priority one
        if not metadata["location"] and potential_locations:
            metadata["location"] = potential_locations[0][1]
            if debug:
                logger.debug(f"Setting location from best pattern match: {metadata['location']}")

    # If we're including end_idx and didn't find a natural end
    if include_end_idx and end_idx == 0 and len(elements) > 10:
        end_idx = 10

    if include_end_idx:
        return metadata, end_idx
    return metadata


def is_person_name(text: str) -> bool:
    """Check if text is likely a person name."""
    # Person names are usually short, capitalized and contain a space
    words = text.split()

    # Structural characteristics of names:
    # 1. Usually 2-3 words (first/last name or first/middle/last)
    # 2. Not too long overall (real names aren't paragraphs)
    # 3. Words in names are typically capitalized
    # 4. Names don't contain typical non-name indicators

    if len(text) > 40 or len(text) < 3:
        return False

    # Must have at least two words
    if len(words) < 2:
        return False

    # Check if words look like a name (most words capitalized)
    capitalized_words = sum(1 for word in words if word and word[0].isupper())
    if capitalized_words < len(words) * 0.75:  # At least 75% of words should be capitalized
        return False

    # Check for patterns that are definitely not names
    text_lower = text.lower()
    if any(indicator in text_lower for indicator in NON_NAME_INDICATORS):
        return False

    # Avoid locations that look like names
    if any(loc in text_lower for loc in LOCATION_INDICATORS):
        return False

    return True


def is_job_title(text: str) -> bool:
    """Check if text is likely a job title."""
    text_lower = text.lower()

    # 1. Direct relationship indicators between person and organization
    if any(rel in text_lower for rel in RELATIONSHIP_INDICATORS):
        # Additional check for org name after relationship indicator
        for rel in RELATIONSHIP_INDICATORS:
            if rel in text_lower:
                # Most job titles with these patterns are legitimate
                return True

    # 2. Check if any role term is present (with word boundaries)
    all_roles = []
    for role_type in COMMON_ROLE_PATTERNS.values():
        all_roles.extend(role_type)

    if any(
        role in text_lower.split() or f"{role}," in text_lower or f"{role}." in text_lower
        for role in all_roles
    ):
        return True

    if any(f"{role} " in text_lower or f" {role}" in text_lower for role in all_roles):
        return True

    # 3. LinkedIn-specific formatting patterns
    if "•" in text and len(text) < 50:  # LinkedIn often uses bullets in titles
        return True

    if " | " in text and not any(x in text_lower for x in CONNECTION_PATTERNS["degree"]):
        return True

    # 4. Common LinkedIn job title patterns like "X at Y" or "X of Y"
    words = text_lower.split()
    if len(words) >= 3:
        for i in range(len(words) - 2):
            if words[i + 1] in ["at", "of", "for", "with"] and words[i] not in [
                "university",
                "school",
                "college",
            ]:
                return True

    return False


def is_connection_info(text: str) -> bool:
    """Check if text contains connection information."""
    text_lower = text.lower()

    # Connection degree indicators
    if any(x in text_lower for x in CONNECTION_PATTERNS["degree"]):
        return True

    # Mutual connection patterns
    if any(x in text_lower for x in CONNECTION_PATTERNS["mutual"]):
        return True

    # Connection count patterns
    if ("follower" in text_lower or "following" in text_lower) and any(
        char.isdigit() for char in text
    ):
        return True

    # Specific LinkedIn connection phrases
    if any(phrase in text_lower for phrase in CONNECTION_PATTERNS["phrases"]):
        return True

    return False
