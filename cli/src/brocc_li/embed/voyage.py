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
from brocc_li.utils.image_utils import image_to_base64, is_plain_text, is_url
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
    batch_size: int
        Number of items to process in a single batch
    api_url: Optional[str]
        URL to the Voyage API endpoint. If not provided, uses API_URL from environment.
    """

    name: str = "voyage-multimodal-3"
    api_url: str = ""  # Default empty string, will be updated in __init__
    batch_size: int = 32
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
            # Prepare the request
            headers = {
                "Content-Type": "application/json",
            }
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

    def _process_image(self, image) -> dict[str, Any]:
        """
        Process an image input into the format expected by the API

        Parameters
        ----------
        image : str, bytes, or PIL.Image.Image
            The image to process

        Returns
        -------
        Dict[str, Any]
            Dictionary with the properly formatted image content
        """
        # If it's a URL, use it directly for image_url type
        if isinstance(image, str) and is_url(image):
            return {"type": ContentType.IMAGE_URL, "image_url": image}

        # For all other cases, try to convert to base64
        try:
            # Convert the image to base64
            base64_str = image_to_base64(image)
            return {"type": ContentType.IMAGE_BASE64, "image_base64": base64_str}
        except Exception as e:
            # If all else fails and it's a string, treat as text
            if isinstance(image, str):
                return {"type": ContentType.TEXT, "text": image}
            else:
                raise RuntimeError(f"Failed to process image: {str(e)}") from e

    def _prepare_multimodal_content(self, content_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a content item to ensure it's in the correct format for the API.

        Parameters
        ----------
        content_item : Dict[str, Any]
            A content item with 'type' and type-specific fields

        Returns
        -------
        Dict[str, Any]
            Content item formatted for the API
        """
        if not isinstance(content_item, dict) or "type" not in content_item:
            # If not properly formatted, try to handle as plain text
            if isinstance(content_item, str):
                return {"type": ContentType.TEXT, "text": content_item}
            # For unhandled types, log warning and return as-is
            logger.warning(f"Unknown content type: {type(content_item)}")
            return content_item

        # Handle known content types
        content_type = content_item["type"]
        if content_type == ContentType.TEXT and "text" in content_item:
            return content_item
        elif content_type == ContentType.IMAGE_URL and "image_url" in content_item:
            return content_item
        elif content_type == ContentType.IMAGE_BASE64 and "image_base64" in content_item:
            return content_item
        else:
            # Try to handle with best effort
            if "image_url" in content_item:
                return {"type": ContentType.IMAGE_URL, "image_url": content_item["image_url"]}
            elif "text" in content_item:
                return {"type": ContentType.TEXT, "text": content_item["text"]}

        # If we get here, we couldn't process the item
        logger.warning(f"Could not process content item: {content_item}")
        return content_item

    def _prepare_structured_input(self, input_data: Union[str, bytes, Dict, Any]) -> Dict[str, Any]:
        """
        Prepare input data in the structured format expected by the API.

        Parameters
        ----------
        input_data : Union[str, bytes, Dict, Any]
            Input data which can be plain text, image, or already structured content

        Returns
        -------
        Dict[str, Any]
            Properly structured input for the API
        """
        # If already structured with 'content' field, validate and return
        if isinstance(input_data, dict) and "content" in input_data:
            # Ensure each content item is properly formatted
            if isinstance(input_data["content"], list):
                input_data["content"] = [
                    self._prepare_multimodal_content(item) for item in input_data["content"]
                ]
            return input_data

        # Handle plain text
        if is_plain_text(input_data):
            return {"content": [{"type": ContentType.TEXT, "text": input_data}]}

        # Handle image
        return {"content": [self._process_image(input_data)]}

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
        """
        # Prepare structured input
        structured_input = self._prepare_structured_input(query)

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
        """
        # Use the imported sanitize_input function which already handles numpy arrays
        inputs = sanitize_input(inputs)

        # Process all inputs
        structured_inputs = []
        for item in inputs:
            structured_inputs.append(self._prepare_structured_input(item))

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
