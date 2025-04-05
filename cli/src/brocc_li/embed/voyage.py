import json
import urllib.request
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    List,
    TypeVar,
    Union,
)
from urllib.error import URLError

from lancedb.embeddings.base import EmbeddingFunction
from lancedb.embeddings.registry import register

from brocc_li.utils.api_url import get_api_url
from brocc_li.utils.auth_data import load_auth_data
from brocc_li.utils.image_utils import (
    SUPPORTED_MIME_TYPES,
    ImageFormat,
    image_to_base64,
    is_plain_text,
    is_supported_mime_type,
    is_url,
)
from brocc_li.utils.logger import logger
from brocc_li.utils.serde import sanitize_input

# Type checking imports
if TYPE_CHECKING:
    try:
        from PIL.Image import Image as PILImage
    except ImportError:
        PILImage = Any  # Fallback if PIL is not available

# Create a type variable for sanitize_input return type
T = TypeVar("T")


class ContentType:
    TEXT = "text"
    IMAGE_URL = "image_url"
    IMAGE_BASE64 = "image_base64"


class InputType:
    QUERY = "query"
    DOCUMENT = "document"


@register("voyageai")
class VoyageAIEmbeddingFunction(EmbeddingFunction):
    """
    An embedding function that uses the VoyageAI API via our custom endpoint

    Parameters
    ----------
    name: str
        The name of the model to use. Currently only supports:
            * voyage-multimodal-3
    api_url: Optional[str]
        URL to the Voyage API endpoint. If not provided, uses API_URL from environment.
    """

    name: str = "voyage-multimodal-3"
    api_url: str = ""  # Default empty string, will be updated in __init__
    dimensions: ClassVar[dict[str, int]] = {
        "voyage-multimodal-3": 1024,
    }

    def __init__(
        self,
        name: str = "voyage-multimodal-3",
        **kwargs,
    ):
        # Call parent class __init__ first to initialize Pydantic
        super().__init__(**kwargs)

        # Set our attributes (don't use direct attribute setting for Pydantic fields)
        self.name = name

        # Use provided API URL or get from environment
        api_url_value = get_api_url()
        # Add /embed path
        api_url_value = f"{api_url_value.rstrip('/')}/embed"

        self.api_url = api_url_value

        # Ensure we have a valid model
        if self.name not in self.dimensions:
            valid_models = ", ".join(self.dimensions.keys())
            raise ValueError(f"Model {self.name} not supported. Valid models: {valid_models}")

    def ndims(self) -> int:
        """Return the dimensions of the embeddings produced by this model"""
        return self.dimensions.get(self.name, 1024)

    def _call_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Call the API with the given payload"""
        try:
            # Load auth data to get API key
            auth_data = load_auth_data()
            if not auth_data or "apiKey" not in auth_data or not auth_data["apiKey"]:
                raise RuntimeError("No API key found. Please login first using 'brocc login'")

            api_key = auth_data["apiKey"]

            # Prepare the request with auth header
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
            data = json.dumps(payload).encode("utf-8")

            # Create request object
            req = urllib.request.Request(self.api_url, data=data, headers=headers, method="POST")

            # Make the request
            with urllib.request.urlopen(req) as response:
                response_data = json.loads(response.read().decode("utf-8"))
                return response_data

        except URLError as e:
            raise RuntimeError(f"Failed to call embedding API: {str(e)}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError("Failed to parse API response") from e

    def _process_image(self, image) -> dict[str, Any] | None:
        """
        Process an image input into the format expected by the API

        Parameters
        ----------
        image : str, bytes, or PIL.Image.Image
            The image to process

        Returns
        -------
        Dict[str, Any] | None
            Dictionary with the properly formatted image content, or None if processing failed
        """
        # If it's a URL, use it directly for image_url type
        if isinstance(image, str) and is_url(image):
            return {"type": ContentType.IMAGE_URL, "image_url": image}

        # Check if it's already a data URL formatted base64 string
        if isinstance(image, str) and image.startswith("data:image/"):
            # Validate format - must be data:image/(png|jpeg|webp|gif);base64,...
            try:
                media_type = image.split(";")[0].split(":")[1]
                if media_type in SUPPORTED_MIME_TYPES and ";base64," in image:
                    return {"type": ContentType.IMAGE_BASE64, "image_base64": image}
                logger.warning(f"Unsupported image format: {media_type}. Using default format.")
            except (IndexError, ValueError):
                pass  # Fall through to normal processing

        # For all other cases, try to convert to base64
        try:
            # Convert the image to base64 with data URL format using PNG by default
            # PNG is the most widely supported format
            base64_str = image_to_base64(image, format=ImageFormat.PNG)
            return {"type": ContentType.IMAGE_BASE64, "image_base64": base64_str}
        except Exception as e:
            # If we can't process the image, return None to indicate failure
            logger.error(f"Failed to process image: {str(e)}")
            return None

    def _prepare_multimodal_content(self, content_item: Dict[str, Any]) -> Dict[str, Any] | None:
        """
        Process a content item to ensure it's in the correct format for the API.

        Parameters
        ----------
        content_item : Dict[str, Any]
            A content item with 'type' and type-specific fields

        Returns
        -------
        Dict[str, Any] | None
            Content item formatted for the API, or None if it couldn't be processed
        """
        if not isinstance(content_item, dict) or "type" not in content_item:
            # If not properly formatted, try to handle as plain text
            if isinstance(content_item, str):
                return {"type": ContentType.TEXT, "text": content_item}
            # For unhandled types, log warning and return None
            logger.warning(f"Unknown content type: {type(content_item)}")
            return None

        # Handle known content types
        content_type = content_item["type"]
        if content_type == ContentType.TEXT and "text" in content_item:
            return content_item
        elif content_type == ContentType.IMAGE_URL and "image_url" in content_item:
            return content_item
        elif content_type == ContentType.IMAGE_BASE64 and "image_base64" in content_item:
            # Validate base64 format
            image_data = content_item["image_base64"]
            if not isinstance(image_data, str) or not image_data.startswith("data:image/"):
                # Try to reformat if possible
                try:
                    if isinstance(image_data, str) and "," not in image_data:
                        # Assume it's just base64 data without the data URL prefix
                        content_item["image_base64"] = f"data:image/png;base64,{image_data}"
                        logger.debug("Reformatted base64 data to include data URL prefix")
                    else:
                        logger.warning(f"Invalid image_base64 format: {image_data[:30]}...")
                        return None
                except Exception:
                    logger.warning("Failed to correct image_base64 format")
                    return None
            else:
                # Verify the MIME type is supported
                try:
                    media_type = image_data.split(";")[0].split(":")[1]
                    if not is_supported_mime_type(media_type):
                        logger.warning(f"Unsupported image format: {media_type}. Request may fail.")
                except (IndexError, ValueError):
                    logger.warning("Could not parse MIME type from data URL")
            return content_item
        else:
            # Try to handle with best effort
            if "image_url" in content_item:
                return {"type": ContentType.IMAGE_URL, "image_url": content_item["image_url"]}
            elif "text" in content_item:
                return {"type": ContentType.TEXT, "text": content_item["text"]}

        # If we get here, we couldn't process the item
        logger.warning(f"Could not process content item: {content_item}")
        return None

    def _prepare_structured_input(
        self, input_data: Union[str, bytes, Dict, Any]
    ) -> Dict[str, Any] | None:
        """
        Prepare input data in the structured format expected by the API.

        Parameters
        ----------
        input_data : Union[str, bytes, Dict, Any]
            Input data which can be plain text, image, or already structured content

        Returns
        -------
        Dict[str, Any] | None
            Properly structured input for the API, or None if input couldn't be processed
        """
        # If already structured with 'content' field, validate and return
        if isinstance(input_data, dict) and "content" in input_data:
            # Ensure each content item is properly formatted
            if isinstance(input_data["content"], list):
                processed_content = []
                for item in input_data["content"]:
                    processed_item = self._prepare_multimodal_content(item)
                    if processed_item:
                        processed_content.append(processed_item)

                # Only return if we have valid content
                if processed_content:
                    input_data["content"] = processed_content
                    return input_data
                else:
                    logger.warning("No valid content items found in structured input")
                    return None
            return input_data

        # Handle plain text
        if is_plain_text(input_data):
            return {"content": [{"type": ContentType.TEXT, "text": input_data}]}

        # Handle image
        image_content = self._process_image(input_data)
        if image_content:
            return {"content": [image_content]}

        # If we couldn't process the input, return None
        logger.warning("Could not process input data")
        return None

    def compute_query_embeddings(
        self,
        query: Union[str, bytes, Dict[str, Any], Any],  # Plain text, image, or structured content
        *args,
        **kwargs,
    ) -> list[list[float]]:
        """
        Compute embeddings for a query, which can be text, an image, or structured content.

        Parameters
        ----------
        query : Union[str, bytes, Dict, Any]
            The query to embed. Can be text, image, or a structured content object.

        Raises
        ------
        RuntimeError
            If the query couldn't be processed or the API returns no embeddings
        """
        # Prepare structured input
        structured_input = self._prepare_structured_input(query)
        if not structured_input:
            raise RuntimeError("Could not process query input")

        payload = {
            "inputs": [structured_input],
            "model": self.name,
            "input_type": InputType.QUERY,
        }

        response = self._call_api(payload)
        if "embeddings" not in response or not response["embeddings"]:
            raise RuntimeError("No embeddings returned from API")

        return response["embeddings"]

    def compute_source_embeddings(
        self,
        inputs: Union[str, List[str], List[bytes], List[Dict[str, Any]], List[Any]],
        *args,
        **kwargs,
    ) -> list[list[float]]:
        """
        Compute embeddings for a list of inputs which can be text, images, or structured content.

        Parameters
        ----------
        inputs : Union[str, List[str], List[bytes], List[Dict], List[Any]]
            List of inputs to embed. Can be text, images, or structured content objects.

        Raises
        ------
        RuntimeError
            If no inputs could be processed or the API returns no embeddings
        """
        # Use the imported sanitize_input function which already handles numpy arrays
        inputs = sanitize_input(inputs)

        # Process all inputs
        structured_inputs = []
        for item in inputs:
            processed = self._prepare_structured_input(item)
            if processed:
                structured_inputs.append(processed)
            else:
                logger.warning("Skipping input that couldn't be processed")

        if not structured_inputs:
            raise RuntimeError("Could not process any inputs")

        # Call API with all inputs
        payload = {
            "inputs": structured_inputs,
            "model": self.name,
            "input_type": InputType.DOCUMENT,
        }

        response = self._call_api(payload)
        if "embeddings" not in response or not response["embeddings"]:
            raise RuntimeError("No embeddings returned from API")

        return response["embeddings"]
