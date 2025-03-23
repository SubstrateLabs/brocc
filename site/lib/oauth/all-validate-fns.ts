import { ValidateOAuthCodeFn } from "./provider-interface";
import { validateOAuthCode as validateNotionOAuthCode } from "./providers/notion";
import { validateOAuthCode as validateGoogleOAuthCode } from "./providers/google";
import { validateOAuthCode as validateSlackOAuthCode } from "./providers/slack";

export const VALIDATE_FUNCTIONS: Record<string, ValidateOAuthCodeFn> = {
  notion: validateNotionOAuthCode,
  google: validateGoogleOAuthCode,
  slack: validateSlackOAuthCode,
};
