/**
 * Minimal retry helper with exponential backoff.
 * Retries the given asyncOperation up to maxRetries times.
 * On each failure, logs the error, waits for (baseDelay * 2^attemptIndex) ms, then tries again.
 */
export async function withRetry<T>(asyncOperation: () => Promise<T>, maxRetries = 2, baseDelay = 250): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await asyncOperation();
    } catch (err) {
      lastError = err;
      console.warn(`[withRetry] attempt=${attempt} failed, err=`, err);
      if (attempt < maxRetries) {
        const delay = baseDelay * 2 ** attempt;
        console.debug(`[withRetry] waiting ${delay}ms before retry...`);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }
  throw lastError; // all retries exhausted
}
