import type { TokenStore } from "./token-store";
import type { CookieStore } from "./cookie-store";
import { OAuth2RequestError, ArcticFetchError } from "arctic";
import { VALIDATE_FUNCTIONS } from "./all-validate-fns";
import { type OauthProvider } from "@/lib/oauth/types";

export enum HandleCallbackRes {
  Success = "success",
  InvalidOAuthParams = "invalid_params",
  UnexpectedError = "unexpected_error",
}

export async function handleCallback({
  domain,
  userId,
  tokenStore,
  cookieStore,
  code,
  scope,
}: {
  domain: OauthProvider;
  userId: string;
  tokenStore: TokenStore;
  cookieStore: CookieStore;
  code: string;
  scope: string;
}): Promise<HandleCallbackRes> {
  try {
    const res = await VALIDATE_FUNCTIONS[domain]({ code, cookieStore });
    if (!res.refreshToken) {
      // Potential issue if we don't have a saved refresh token
      // but some providers (e.g. notion) don't support refresh tokens
      console.warn("Missing refresh token");
    }
    await tokenStore.saveTokenData({
      domain,
      data: {
        accessToken: res.accessToken,
        accessTokenExpiresAt: res.accessTokenExpiresAt,
        refreshToken: res.refreshToken,
        providerMetadata: res.providerMetadata,
      },
      workosUserId: userId,
      account: res.account,
      // note: some providers (e.g. slack) don't return scope in validate response
      scope,
    });
    return HandleCallbackRes.Success;
  } catch (error) {
    if (error instanceof OAuth2RequestError) {
      console.error(`Invalid OAuth params ${error.code}`);
      return HandleCallbackRes.InvalidOAuthParams;
    }
    if (error instanceof ArcticFetchError) {
      console.error(`Arctic fetch error ${error}`);
    } else {
      console.error(`Unexpected error ${error}`);
    }
    return HandleCallbackRes.UnexpectedError;
  }
}
