import {
  S3Client,
  PutObjectCommand,
  DeleteObjectCommand,
  ListObjectsV2Command,
  DeleteObjectsCommand,
} from "@aws-sdk/client-s3";
import { getEnvVar } from "./get-env-var";

// Strip the bucket name from the base URL for S3 client
const r2BaseUrl = getEnvVar("R2_BASE_URL").replace(/\/[^/]+$/, "");

const s3 = new S3Client({
  region: process.env.R2_REGION ?? "auto",
  credentials: {
    accessKeyId: getEnvVar("R2_ACCESS_KEY_ID"),
    secretAccessKey: getEnvVar("R2_SECRET_ACCESS_KEY"),
  },
  endpoint: r2BaseUrl,
});

// https://dash.cloudflare.com/3a57cbd5684eb756bbde7ce44a3e3ed5/r2/default/buckets/broccolink/settings
const PUBLIC_BASE_URL = "https://brc.ink";

/**
 * Store (overwrite) the object at the given l;cation
 * Returns the public URL after we upload or overwrite the file.
 */
export async function storeFile(
  key: string,
  data: Buffer | string,
  contentType: string,
  directory: string,
): Promise<string> {
  const bucket = getEnvVar("R2_BUCKET_NAME");
  const size = typeof data === "string" ? Buffer.byteLength(data, "utf8") : data.byteLength;
  const sizeMb = size / (1024 * 1024);
  const fullKey = `${directory}/${key}`;
  console.log(`storing file ${fullKey}, size: ${sizeMb.toFixed(2)} MB`);

  try {
    await s3.send(
      new PutObjectCommand({
        Bucket: bucket,
        Key: fullKey,
        Body: data,
        ContentType: contentType,
      }),
    );
    console.log(`stored file ${fullKey}, size: ${sizeMb.toFixed(2)} MB`);
  } catch (error) {
    console.error(`Error storing file ${fullKey}:`, error);
    throw error;
  }

  return `${PUBLIC_BASE_URL}/${fullKey}`;
}

/**
 * Delete file at the given location
 * @param key
 * @param directory
 */
export async function deleteFile(key: string, directory: string): Promise<void> {
  const bucket = getEnvVar("R2_BUCKET_NAME");
  const fullKey = `${directory}/${key}`;
  console.log(`deleting file ${fullKey}`);

  try {
    await s3.send(
      new DeleteObjectCommand({
        Bucket: bucket,
        Key: fullKey,
      }),
    );
    console.log(`deleted file ${fullKey}`);
  } catch (error) {
    console.error(`Error deleting file ${fullKey}:`, error);
    throw error;
  }
}

/**
 * Lists all objects in the bucket
 */
export async function listAllObjects(): Promise<string[]> {
  const bucket = getEnvVar("R2_BUCKET_NAME");
  console.log(`📋 Listing all objects in bucket ${bucket}...`);

  try {
    const command = new ListObjectsV2Command({
      Bucket: bucket,
    });

    const response = await s3.send(command);
    const objects = response.Contents?.map((obj) => obj.Key || "") || [];
    console.log(`Found ${objects.length} objects`);
    return objects;
  } catch (error) {
    console.error("Error listing objects:", error);
    throw error;
  }
}

/**
 * Deletes all objects in the bucket
 */
export async function deleteAllObjects(): Promise<void> {
  const bucket = getEnvVar("R2_BUCKET_NAME");
  console.log(`🧹 Deleting all objects in bucket ${bucket}...`);

  try {
    const objects = await listAllObjects();
    if (objects.length === 0) {
      console.log("No objects to delete");
      return;
    }

    const command = new DeleteObjectsCommand({
      Bucket: bucket,
      Delete: {
        Objects: objects.map((Key) => ({ Key })),
        Quiet: false,
      },
    });

    const response = await s3.send(command);
    console.log(`Deleted ${response.Deleted?.length || 0} objects`);
    if (response.Errors) {
      console.error("Errors during deletion:", response.Errors);
    }
  } catch (error) {
    console.error("Error deleting objects:", error);
    throw error;
  }
}
