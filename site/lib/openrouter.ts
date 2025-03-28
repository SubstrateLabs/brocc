/**
 * OpenRouter admin APIs: https://openrouter.ai/docs/features/provisioning-api-keys
 */
import { getEnvVar } from "./get-env-var";

const provisioningKey = getEnvVar("OPENROUTER_PROVISIONING_KEY");
const BASE_URL = "https://openrouter.ai/api/v1/keys";

export interface OpenRouterKey {
  name: string;
  label?: string;
  limit?: number;
  disabled?: boolean;
  created_at?: string;
  updated_at?: string;
  hash?: string;
  key?: string;
  usage?: number;
}

export interface ListKeysResponse {
  data: OpenRouterKey[];
}

export interface ListKeysParams {
  offset?: number;
  include_disabled?: boolean;
}

const headers = {
  Authorization: `Bearer ${provisioningKey}`,
  "Content-Type": "application/json",
};

export async function listKeys(params: ListKeysParams = {}): Promise<ListKeysResponse> {
  const { offset = 0, include_disabled } = params;
  const queryParams = new URLSearchParams();
  if (offset) queryParams.append("offset", offset.toString());
  if (include_disabled !== undefined) queryParams.append("include_disabled", include_disabled.toString());
  
  const response = await fetch(`${BASE_URL}?${queryParams}`, { headers });
  if (!response.ok) throw new Error(`Failed to list keys: ${response.statusText}`);
  return response.json();
}

export async function createKey(key: OpenRouterKey): Promise<OpenRouterKey> {
  const response = await fetch(BASE_URL, {
    method: "POST",
    headers,
    body: JSON.stringify(key),
  });
  if (!response.ok) throw new Error(`Failed to create key: ${response.statusText}`);
  return response.json();
}

export async function getKey(keyHash: string): Promise<OpenRouterKey> {
  const response = await fetch(`${BASE_URL}/${keyHash}`, { headers });
  if (!response.ok) throw new Error(`Failed to get key: ${response.statusText}`);
  return response.json();
}

export async function updateKey(keyHash: string, updates: Partial<OpenRouterKey>): Promise<OpenRouterKey> {
  const response = await fetch(`${BASE_URL}/${keyHash}`, {
    method: "PATCH",
    headers,
    body: JSON.stringify(updates),
  });
  if (!response.ok) throw new Error(`Failed to update key: ${response.statusText}`);
  return response.json();
}

export async function deleteKey(keyHash: string): Promise<void> {
  const response = await fetch(`${BASE_URL}/${keyHash}`, {
    method: "DELETE",
    headers,
  });
  if (!response.ok) throw new Error(`Failed to delete key: ${response.statusText}`);
}
