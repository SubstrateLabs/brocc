import { type OauthProvider } from "@/lib/oauth/types";

/**
 * Always save the access token (which may be short-lived).
 * Make sure you also save the long-lived token (provider-specific).
 * Also save provider-specific metadata
 * @field accessTokenExpiresAt: not all access tokens expire
 * @field refreshToken: for refresh tokens + expiring access token
 */
export interface TokenData {
  accessToken: string;
  accessTokenExpiresAt?: string | null;
  refreshToken?: string | null;
  providerMetadata?: Record<string, unknown> | null;
}

/**
 * @field account unique identifier e.g. "ben@substrate.run"
 * @field scope space-separated scope string from oauth callback
 * @field cursor pagination cursor for incremental syncs
 * @field lastUpdated ISO timestamp of last successful sync
 */
export interface TokenAccount {
  account: string;
  scope?: string | null;
  linkCursor?: string | null;
  lastUpdated?: string | null;
  providerMetadata?: Record<string, unknown> | null;
}

const PREFIX = "oauth";

export abstract class TokenStore {
  protected abstract getAccounts(key: string): Promise<TokenAccount[]>;
  protected abstract setAccounts(key: string, accounts: TokenAccount[]): Promise<void>;
  protected abstract getData(key: string): Promise<TokenData | null>;
  protected abstract setData(key: string, data: TokenData | null): Promise<void>;
  protected abstract removeData(key: string): Promise<void>;
  protected abstract updateAccount(key: string, account: string, update: Partial<TokenAccount>): Promise<void>;

  /**
   * Update an account's cursor and lastUpdated timestamp
   */
  async updateCursor({
    domain,
    account,
    workosUserId,
    linkCursor,
  }: {
    domain: OauthProvider;
    account: string;
    workosUserId: string;
    linkCursor?: string | null;
  }): Promise<void> {
    const key = this.accountsKey(domain, workosUserId);
    await this.updateAccount(key, account, {
      linkCursor: linkCursor,
      lastUpdated: new Date().toISOString(),
    });
  }

  /**
   * Clear an account's cursor and lastUpdated timestamp
   */
  async clearSync({
    domain,
    account,
    workosUserId,
  }: {
    domain: OauthProvider;
    account: string;
    workosUserId: string;
  }): Promise<void> {
    const key = this.accountsKey(domain, workosUserId);
    await this.updateAccount(key, account, {
      linkCursor: null,
      lastUpdated: null,
    });
  }

  /**
   * Update an account's provider metadata
   */
  async updateProviderMetadata({
    domain,
    account,
    workosUserId,
    providerMetadata,
  }: {
    domain: OauthProvider;
    account: string;
    workosUserId: string;
    providerMetadata: Record<string, unknown> | null;
  }): Promise<void> {
    const key = this.accountsKey(domain, workosUserId);
    await this.updateAccount(key, account, {
      providerMetadata,
    });
  }

  /**
   * Remove the account and all associated tokens
   */
  async removeTokenAccount({
    domain,
    account,
    workosUserId,
  }: {
    domain: OauthProvider;
    account: string;
    workosUserId: string;
  }) {
    const accountsKey = this.accountsKey(domain, workosUserId);
    const accounts = await this.getAccounts(accountsKey);

    if (accounts) {
      const accountIndex = accounts.findIndex((a) => a.account === account);
      if (accountIndex !== -1) {
        accounts.splice(accountIndex, 1);
        if (accounts.length > 0) {
          await this.setAccounts(accountsKey, accounts);
        } else {
          await this.removeData(accountsKey);
        }
      } else {
        console.warn(`account not registered: ${account}`);
      }
    }
    const dataKey = this.dataKey(domain, account, workosUserId);
    const data = await this.getData(dataKey);
    if (data) {
      await this.removeData(dataKey);
    } else {
      console.warn(`no token data for account: ${account}`);
    }
  }

  async getTokenAccounts({
    domain,
    workosUserId,
  }: {
    domain: OauthProvider;
    workosUserId: string;
  }): Promise<TokenAccount[]> {
    const key = this.accountsKey(domain, workosUserId);
    const accounts = await this.getAccounts(key);
    return accounts || [];
  }

  async saveTokenData({
    domain,
    data,
    account,
    workosUserId,
    scope,
  }: {
    domain: OauthProvider;
    data: TokenData;
    account: string;
    workosUserId: string;
    scope: string;
  }) {
    await this.registerTokenAccount({
      domain,
      account,
      workosUserId,
      scope,
      providerMetadata: data.providerMetadata,
    });
    const key = this.dataKey(domain, account, workosUserId);
    await this.setData(key, data);
  }

  async getTokenData({
    domain,
    account,
    workosUserId,
  }: {
    domain: OauthProvider;
    account: string;
    workosUserId: string;
  }): Promise<TokenData | null> {
    const key = this.dataKey(domain, account, workosUserId);
    return await this.getData(key);
  }

  protected async registerTokenAccount({
    domain,
    account,
    workosUserId,
    scope,
    providerMetadata,
  }: {
    domain: OauthProvider;
    account: string;
    workosUserId: string;
    scope?: string | null;
    providerMetadata?: Record<string, unknown> | null;
  }) {
    const key = this.accountsKey(domain, workosUserId);
    const accounts = await this.getAccounts(key);

    if (accounts.length) {
      const existingAccount = accounts.find((a) => a.account === account);
      if (existingAccount) {
        existingAccount.scope = scope;
        await this.setAccounts(key, accounts);
      } else {
        accounts.push({ account, scope, providerMetadata });
        await this.setAccounts(key, accounts);
      }
    } else {
      await this.setAccounts(key, [{ account, scope, providerMetadata }]);
    }
  }

  protected accountsKey = (domain: string, workosUserId: string): string => {
    return `${PREFIX}.${domain}.accounts::${workosUserId}`;
  };

  protected readonly dataKey = (domain: OauthProvider, workosUserId: string, account: string): string => {
    return `${PREFIX}.${domain}::${account}::${workosUserId}`;
  };
}
