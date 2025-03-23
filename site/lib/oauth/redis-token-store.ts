import { Redis } from "@upstash/redis";
import { TokenStore, type TokenAccount, type TokenData } from "./token-store";
import { getEnvVar } from "../get-env-var";

export class RedisTokenStore extends TokenStore {
  private redis: Redis;

  constructor() {
    super();
    this.redis = new Redis({
      url: getEnvVar("REDIS_URL"),
      token: getEnvVar("REDIS_TOKEN"),
    });
  }

  protected async getAccounts(key: string): Promise<TokenAccount[]> {
    const val = await this.redis.get(key);
    return (val as TokenAccount[]) || [];
  }

  protected async setAccounts(key: string, accounts: TokenAccount[]): Promise<void> {
    await this.redis.set(key, accounts);
  }

  protected async getData(key: string): Promise<TokenData | null> {
    const data = await this.redis.get(key);
    return data as TokenData | null;
  }

  protected async setData(key: string, data: TokenData | null): Promise<void> {
    await this.redis.set(key, data);
  }

  protected async removeData(key: string): Promise<void> {
    await this.redis.del(key);
  }

  protected async updateAccount(key: string, account: string, update: Partial<TokenAccount>): Promise<void> {
    const accounts = await this.getAccounts(key);
    const accountIndex = accounts.findIndex((a) => a.account === account);

    if (accountIndex === -1) {
      throw new Error(`Account ${account} not found in ${key}`);
    }

    accounts[accountIndex] = {
      ...accounts[accountIndex],
      ...update,
    };

    await this.setAccounts(key, accounts);
  }
}
