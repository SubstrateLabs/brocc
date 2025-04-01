https://docs.voyageai.com/docs/multimodal-embeddings
https://docs.voyageai.com/reference/multimodal-embeddings-api

(1) Build a TS endpoint that hits voyage

`inputs`

Each input is a sequence of text and images, which can be represented in either of the following two ways:

(1) A list containing text strings and/or PIL image objects (List[Union[str, PIL.Image.Image]]), where each image is an instance of the Pillow Image class. For example: ["This is a banana.", PIL.Image.open("banana.jpg")].

_Note: seems like Lance can read image urls and translate to PIL_

The following constraints apply to the inputs list:
The list must not contain more than 1000 inputs.
Each image must not contain more than 16 million pixels or be larger than 20 MB in size.
With every 560 pixels of an image being counted as a token, each input in the list must not exceed 32,000 tokens, and the total number of tokens across all inputs must not exceed 320,000.

`input_type`

When input_type is None, the embedding model directly converts the inputs into numerical vectors. For retrieval/search purposes, where a "query", which can be text or image in this case, is used to search for relevant information among a collection of data referred to as "documents," we recommend specifying whether your inputs are intended as queries or documents by setting input_type to query or document, respectively. In these cases, Voyage automatically prepends a prompt to your inputs before vectorizing them, creating vectors more tailored for retrieval/search tasks. Since inputs can be multimodal, "queries" and "documents" can be text, images, or an interleaving of both modalities. Embeddings generated with and without the input_type argument are compatible.
For transparency, the following prompts are prepended to your input.
For query, the prompt is "Represent the query for retrieving supporting documents: ".
For document, the prompt is "Represent the document for retrieval: ".

[Reference implementation for voyageai](https://github.com/lancedb/lancedb/blob/a997fd41080be3732def9dd352afbfa65c2fe8c6/python/python/lancedb/embeddings/voyageai.py#L34)
