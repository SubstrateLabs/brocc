import base64
import io
import json
import os
import urllib.request
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    TypeVar,
    cast,
)
from urllib.error import URLError
from urllib.parse import urlparse

from lancedb.embeddings.base import EmbeddingFunction
from lancedb.embeddings.registry import register

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

    def sanitize_input(self, texts: Any) -> list[Any]:
        """
        Sanitize the input to the embedding function.

        Parameters
        ----------
        texts : str, bytes, PIL.Image.Image, list, or other array-like
            The inputs to sanitize

        Returns
        -------
        List[Any]
            Sanitized list of inputs
        """
        # Handle single inputs (convert to list)
        if isinstance(texts, (str, bytes)):
            return [texts]

        # Handle PyArrow Arrays if available
        try:
            import pyarrow as pa

            if isinstance(texts, pa.Array):
                return cast(list[Any], texts.to_pylist())
            elif isinstance(texts, pa.ChunkedArray):
                return cast(list[Any], texts.combine_chunks().to_pylist())
        except ImportError:
            pass  # PyArrow not available, continue

        # Handle numpy arrays if available
        try:
            import numpy as np

            if isinstance(texts, np.ndarray):
                return cast(list[Any], texts.tolist())
        except ImportError:
            pass  # NumPy not available, continue

        # Return as list (assumes it's iterable)
        return list(texts)

    def _to_pil(self, image: str | bytes) -> Any:
        """
        Convert various image formats to PIL Image

        Parameters
        ----------
        image : Union[str, bytes]
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
        if isinstance(image, str):
            parsed = urlparse(image)
            if parsed.scheme.startswith("http"):
                return {"type": ContentType.IMAGE_URL, "image_url": image}

        # For all other cases, try to convert to base64
        try:
            # Convert to PIL first
            pil_image = None

            # First try to use _to_pil which already has proper type handling
            pil_image = self._to_pil(image)

            # Convert PIL to base64
            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format="PNG")
            image_bytes = img_byte_arr.getvalue()
            base64_str = base64.b64encode(image_bytes).decode("utf-8")

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
        if isinstance(query, str) and not (
            query.startswith("http://")
            or query.startswith("https://")
            or query.startswith("file://")
            or os.path.isfile(query)
        ):
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
        inputs = self.sanitize_input(inputs)

        # Process all inputs in a single request
        payload = {
            "inputs": [],
            "model": self.name,
            "input_type": InputType.DOCUMENT,
        }

        # Process each item
        for item in inputs:
            if isinstance(item, str) and not (
                item.startswith("http://")
                or item.startswith("https://")
                or item.startswith("file://")
                or os.path.isfile(item)
            ):
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
