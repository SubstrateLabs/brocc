import { NextRequest, NextResponse } from "next/server";
import { getEnvVar } from "@/lib/get-env-var";
import { requireApiAuth } from "@/lib/api-key-auth";

// DOCS: https://docs.voyageai.com/reference/multimodal-embeddings-api
const VOYAGE_API_URL = "https://api.voyageai.com/v1/multimodalembeddings";

enum ContentType {
  Text = 'text',
  ImageUrl = 'image_url',
  ImageBase64 = 'image_base64'
}

enum InputType {
  Query = 'query',
  Document = 'document'
}

enum OutputEncoding {
  Base64 = 'base64'
}

type ContentItem = {
  type: ContentType;
  text?: string;
  image_url?: string;
  image_base64?: string;
};

type VoyageRequest = {
  inputs: Array<{ content: ContentItem[] }>;
  model?: string;
  input_type?: InputType | null;
  truncation?: boolean;
  output_encoding?: OutputEncoding | null;
};

/**
 * Validates the content of a multimodal input
 * @param content Array of content items (text or images)
 * @param imageType The type of image being used (url or base64)
 * @returns Error message if invalid, null if valid
 */
function validateContent(content: ContentItem[], imageType: 'url' | 'base64' | null): string | null {
  if (!Array.isArray(content)) {
    return 'Content must be an array';
  }

  for (const item of content) {
    if (!Object.values(ContentType).includes(item.type)) {
      return `Content type must be one of: ${Object.values(ContentType).join(', ')}`;
    }

    if (item.type === ContentType.Text && !item.text) {
      return 'Text content must have a "text" field';
    }

    if (item.type === ContentType.ImageUrl && !item.image_url) {
      return 'Image content must have an "image_url" field';
    }

    if (item.type === ContentType.ImageBase64 && !item.image_base64) {
      return 'Image content must have an "image_base64" field';
    }

    // Validate image type consistency
    if (item.type.startsWith('image_')) {
      const currentImageType = item.type === ContentType.ImageUrl ? 'url' : 'base64';
      if (imageType && imageType !== currentImageType) {
        return 'All images in a request must use the same format (either all URLs or all base64)';
      }
    }
  }

  return null;
}

export async function POST(request: NextRequest) {
  // Authenticate request
  const authResult = await requireApiAuth(request);
  if (authResult instanceof NextResponse) {
    return authResult; // Return error response if auth failed
  }
  // const { userId } = authResult;
  
  let apiKey: string;
  try {
    apiKey = getEnvVar("VOYAGE_API_KEY");
  } catch (error) {
    console.error("Failed to get VOYAGE_API_KEY:", error);
    return NextResponse.json(
      { error: "Server configuration error: Missing API key." },
      { status: 500 },
    );
  }

  let requestData: VoyageRequest;
  try {
    requestData = await request.json();
  } catch (error) {
    console.error("Failed to parse request body:", error);
    return NextResponse.json(
      { error: "Invalid request body. Expected JSON." },
      { status: 400 },
    );
  }

  // Validate required fields
  if (!requestData.inputs || !Array.isArray(requestData.inputs)) {
    return NextResponse.json(
      { error: 'Missing or invalid "inputs" array in request body.' },
      { status: 400 },
    );
  }

  // Validate input count limit
  if (requestData.inputs.length > 1000) {
    return NextResponse.json(
      { error: 'Inputs array cannot contain more than 1000 items.' },
      { status: 400 },
    );
  }

  // Validate each input
  let imageType: 'url' | 'base64' | null = null;
  for (const input of requestData.inputs) {
    if (!input.content) {
      return NextResponse.json(
        { error: 'Each input must have a "content" array.' },
        { status: 400 },
      );
    }

    const contentError = validateContent(input.content, imageType);
    if (contentError) {
      return NextResponse.json({ error: contentError }, { status: 400 });
    }

    // Update imageType based on first image found
    for (const item of input.content) {
      if (item.type === ContentType.ImageUrl) {
        imageType = 'url';
        break;
      } else if (item.type === ContentType.ImageBase64) {
        imageType = 'base64';
        break;
      }
    }
  }

  // Validate model
  if (requestData.model && requestData.model !== "voyage-multimodal-3") {
    return NextResponse.json(
      { error: 'Only "voyage-multimodal-3" model is supported.' },
      { status: 400 },
    );
  }

  // Validate input_type if provided
  if (requestData.input_type && !Object.values(InputType).includes(requestData.input_type)) {
    return NextResponse.json(
      { error: `input_type must be one of: ${Object.values(InputType).join(', ')} or null.` },
      { status: 400 },
    );
  }

  // Validate output_encoding if provided
  if (requestData.output_encoding && !Object.values(OutputEncoding).includes(requestData.output_encoding)) {
    return NextResponse.json(
      { error: `output_encoding must be one of: ${Object.values(OutputEncoding).join(', ')} or null.` },
      { status: 400 },
    );
  }

  // Construct payload for Voyage AI
  const voyagePayload = {
    inputs: requestData.inputs,
    model: requestData.model || "voyage-multimodal-3",
    input_type: requestData.input_type,
    truncation: requestData.truncation ?? true,
    output_encoding: requestData.output_encoding,
  };

  try {
    const voyageResponse = await fetch(VOYAGE_API_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(voyagePayload),
    });

    if (!voyageResponse.ok) {
      const errorBody = await voyageResponse.text();
      console.error(
        `Voyage API error: ${voyageResponse.status} ${voyageResponse.statusText}`,
        errorBody,
      );
      return NextResponse.json(
        {
          error: "Failed to get embeddings from external API.",
          details: errorBody,
        },
        { status: voyageResponse.status },
      );
    }

    const voyageData = await voyageResponse.json();
    return NextResponse.json(voyageData);
  } catch (error) {
    console.error("Error calling Voyage API:", error);
    return NextResponse.json(
      { error: "Internal server error while contacting embedding service." },
      { status: 500 },
    );
  }
}
