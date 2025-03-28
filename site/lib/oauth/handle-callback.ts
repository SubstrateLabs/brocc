import type { RedisTokenStore } from "./redis-token-store";
import type { CookieStore } from "./cookie-store";
import { OAuth2RequestError, ArcticFetchError } from "arctic";
import { type OauthProvider } from "@/lib/oauth/providers/oauth-providers";
import { ValidateOAuthCodeFn } from "@/lib/oauth/provider-interface";
import { validateOAuthCode as validateNotionOAuthCode } from "@/lib/oauth/providers/notion";
import { validateOAuthCode as validateGoogleOAuthCode } from "@/lib/oauth/providers/google";
import { validateOAuthCode as validateSlackOAuthCode } from "@/lib/oauth/providers/slack";

export const VALIDATE_FUNCTIONS: Record<string, ValidateOAuthCodeFn> = {
  notion: validateNotionOAuthCode,
  google: validateGoogleOAuthCode,
  slack: validateSlackOAuthCode,
};


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
}: {
  domain: OauthProvider;
  userId: string;
  tokenStore: RedisTokenStore;
  cookieStore: CookieStore;
  code: string;
}): Promise<HandleCallbackRes> {
  try {
    const res = await VALIDATE_FUNCTIONS[domain]({ code, cookieStore });
    if (!res.refreshToken) {
      // TODO: Potential issue if we don't have a saved refresh token add observability here
      // note that some providers (e.g. notion) don't support refresh tokens
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
      userId: userId,
      account: res.account,
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
