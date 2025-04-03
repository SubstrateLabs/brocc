import json
import os
import urllib.request
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    TypeVar,
)
from urllib.error import URLError

from lancedb.embeddings.base import EmbeddingFunction
from lancedb.embeddings.registry import register

from brocc_li.utils.image_utils import image_to_base64, is_plain_text, is_url
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
        batch_size: int = 32,
        api_url: str | None = None,
        **kwargs,
    ):
        # Call parent class __init__ first to initialize Pydantic
        super().__init__(**kwargs)

        # Set our attributes (don't use direct attribute setting for Pydantic fields)
        self.name = name
        self.batch_size = batch_size

        # Use provided API URL or get from environment
        api_url_value = api_url or os.environ.get("API_URL", "")
        if not api_url_value:
            raise ValueError("API_URL environment variable or api_url parameter must be provided")

        # Add /embed path if it doesn't end with it
        if not api_url_value.endswith("/embed"):
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

    def compute_query_embeddings(
        self,
        query: str | bytes | Any,  # PILImage or any image-like object
        *args,
        **kwargs,
    ) -> list[list[float]]:
        """
        Compute embeddings for a query, which can be text or an image

        Parameters
        ----------
        query : Union[str, bytes, Any]
            The query to embed. Can be text, image bytes, or a PIL Image.
        """
        content = []

        # Process query based on type
        if is_plain_text(query):
            # It's a text query
            content.append({"type": ContentType.TEXT, "text": query})
        else:
            # It's an image query
            content.append(self._process_image(query))

        payload = {
            "inputs": [{"content": content}],
            "model": self.name,
            "input_type": InputType.QUERY,
        }

        response = self._call_api(payload)
        if "embeddings" not in response or not response["embeddings"]:
            raise RuntimeError("No embeddings returned from API")

        return response["embeddings"]

    def compute_source_embeddings(
        self,
        inputs: list[str] | list[bytes] | list[Any],  # List of str, bytes, or PILImage objects
        *args,
        **kwargs,
    ) -> list[list[float]]:
        """
        Compute embeddings for a list of inputs (texts or images)

        Parameters
        ----------
        inputs : Union[List[str], List[bytes], List[Any]]
            List of inputs to embed. Can be text, image bytes, or PIL Images.
        """
        # Sanitize inputs
        inputs = sanitize_input(inputs)

        # Process all inputs in a single request
        payload = {
            "inputs": [],
            "model": self.name,
            "input_type": InputType.DOCUMENT,
        }

        # Process each item
        for item in inputs:
            if is_plain_text(item):
                # It's a text item
                payload["inputs"].append({"content": [{"type": ContentType.TEXT, "text": item}]})
            else:
                # It's an image item
                payload["inputs"].append({"content": [self._process_image(item)]})

        # Call API once with all inputs
        response = self._call_api(payload)
        if "embeddings" not in response or not response["embeddings"]:
            raise RuntimeError("No embeddings returned from API")

        return response["embeddings"]
