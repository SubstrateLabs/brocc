import { Redis } from "@upstash/redis";
import { type OauthProvider } from "@/lib/oauth/providers/oauth-providers";
import { getEnvVar } from "../get-env-var";

/**
 * Some providers vend never-expiring access tokens.
 * Others vend short-lived access tokens + refresh tokens.
 * Remember to include provider-specific metadata.
 * @field accessTokenExpiresAt: not all access tokens expire
 * @field refreshToken: for refresh tokens + expiring access token
 */
export interface TokenData {
  accessToken: string;
  accessTokenExpiresAt?: string | null;
  refreshToken?: string | null;
  providerMetadata?: Record<string, unknown> | null;
}


const PREFIX = "oauth";
const TOKEN_TTL = 3600; // 1 hour

export class RedisTokenStore {
  private redis: Redis;

  constructor() {
    this.redis = new Redis({
      url: getEnvVar("REDIS_URL"),
      token: getEnvVar("REDIS_TOKEN"),
    });
  }

  async saveTokenData({
    domain,
    data,
    account,
    userId,
  }: {
    domain: OauthProvider;
    data: TokenData;
    account: string;
    userId: string;
  }) {
    const key = this.dataKey(domain, account, userId);
    await this.setData(key, data);
  }

  async getTokenData({
    domain,
    account,
    userId,
  }: {
    domain: OauthProvider;
    account: string;
    userId: string;
  }): Promise<TokenData | null> {
    const key = this.dataKey(domain, account, userId);
    return await this.getData(key);
  }

  private async getData(key: string): Promise<TokenData | null> {
    const data = await this.redis.get(key);
    return data as TokenData | null;
  }

  private async setData(key: string, data: TokenData | null): Promise<void> {
    await this.redis.set(key, data, { ex: TOKEN_TTL });
  }

  private readonly dataKey = (domain: OauthProvider, account: string, userId: string): string => {
    return `${PREFIX}.${domain}::${account}::${userId}`;
  };
}
