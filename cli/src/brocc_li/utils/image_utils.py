import base64
import enum
import io
import os
import urllib.request
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlparse

# Type checking imports
if TYPE_CHECKING:
    try:
        from PIL.Image import Image as PILImage
    except ImportError:
        PILImage = Any  # Fallback if PIL is not available


class ImageFormat(str, enum.Enum):
    """Supported image formats for Voyage AI embeddings"""

    PNG = "PNG"
    JPEG = "JPEG"
    WEBP = "WEBP"
    GIF = "GIF"


# Mapping of image formats to MIME types
FORMAT_TO_MIME = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
}

# List of MIME types supported by VoyageAI
SUPPORTED_MIME_TYPES = list(set(FORMAT_TO_MIME.values()))


def is_supported_mime_type(mime_type: str) -> bool:
    """
    Check if a MIME type is supported by VoyageAI for image embeddings

    Parameters
    ----------
    mime_type : str
        The MIME type to check

    Returns
    -------
    bool
        True if the MIME type is supported, False otherwise
    """
    return mime_type in SUPPORTED_MIME_TYPES


def url_retrieve(url: str) -> bytes:
    """
    Retrieve content from a URL

    Parameters
    ----------
    url : str
        URL to retrieve

    Returns
    -------
    bytes
        Content of the URL
    """
    with urllib.request.urlopen(url) as response:
        return response.read()


def to_pil(image: str | bytes | Any) -> Any:
    """
    Convert various image formats to PIL Image

    Parameters
    ----------
    image : Union[str, bytes, Any]
        The image to convert. Can be a URL, file path, or raw bytes.

    Returns
    -------
    PIL.Image.Image
        PIL Image object
    """
    try:
        from PIL import Image as PILImage
    except ImportError as e:
        raise ImportError(
            "PIL is required for image processing. Install with 'pip install pillow'"
        ) from e

    # Handle bytes directly
    if isinstance(image, (bytes, bytearray, memoryview)):
        return PILImage.open(io.BytesIO(image if isinstance(image, bytes) else bytes(image)))

    # Handle PIL Image - avoid checking for "save" attribute directly
    try:
        # Check if it's a PIL Image without explicitly importing PIL.Image
        # This is a safer approach than checking for .save attribute
        if hasattr(image, "__class__") and "PIL" in image.__class__.__module__:
            return image
    except Exception:
        pass

    # Handle string (URL or path)
    if isinstance(image, str):
        parsed = urlparse(image)

        # Handle remote URLs
        if parsed.scheme.startswith("http"):
            return PILImage.open(io.BytesIO(url_retrieve(image)))

        # Handle file URLs
        elif parsed.scheme == "file":
            return PILImage.open(parsed.path)

        # Handle local paths
        elif parsed.scheme == "":
            # Handle Windows paths differently
            return PILImage.open(image if os.name == "nt" else parsed.path)

        else:
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

    raise TypeError(f"Unsupported image type: {type(image)}")


def image_to_base64(
    image: str | bytes | Any,
    format: Literal["PNG", "JPEG", "WEBP", "GIF"] | ImageFormat = ImageFormat.PNG,
) -> str:
    """
    Convert an image to base64 encoded string in data URL format

    Parameters
    ----------
    image : Union[str, bytes, Any]
        The image to convert. Can be a URL, file path, PIL Image, or raw bytes.
    format : ImageFormat or Literal["PNG", "JPEG", "WEBP", "GIF"], optional
        The format to save the image as, by default ImageFormat.PNG

    Returns
    -------
    str
        Base64 encoded string of the image in data URL format
        (data:[<mediatype>];base64,<data>) as required by VoyageAI
    """
    # Convert to PIL first
    pil_image = to_pil(image)

    # Handle enum values
    if isinstance(format, ImageFormat):
        format_str = format.value
    else:
        format_str = format

    # Convert PIL to base64
    img_byte_arr = io.BytesIO()
    pil_image.save(img_byte_arr, format=format_str)
    image_bytes = img_byte_arr.getvalue()
    base64_data = base64.b64encode(image_bytes).decode("utf-8")

    # Format according to Voyage AI requirements (data URL format)
    # Map format to mime type
    format_lower = format_str.lower()
    mime_type = FORMAT_TO_MIME.get(format_lower, "image/png")

    # Return in data URL format
    return f"data:{mime_type};base64,{base64_data}"


def is_url(text: str) -> bool:
    """
    Check if a string is a URL

    Parameters
    ----------
    text : str
        The string to check

    Returns
    -------
    bool
        True if the string is a URL, False otherwise
    """
    parsed = urlparse(text)
    # Handle both http/https/ftp URLs and file URLs
    return bool((parsed.scheme and parsed.netloc) or parsed.scheme == "file")


def is_plain_text(item: Any) -> bool:
    """
    Check if an item represents plain text rather than a URL or file path

    Parameters
    ----------
    item : Any
        The item to check

    Returns
    -------
    bool
        True if the item is plain text, False if it's a URL, file path, or non-string
    """
    # Return False for non-string types
    if not isinstance(item, str):
        return False

    # For strings, check if it's NOT a URL or file path
    return not (
        item.startswith("http://")
        or item.startswith("https://")
        or item.startswith("file://")
        or os.path.isfile(item)
    )
