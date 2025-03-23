import { TestOAuthConnectionFn } from "./provider-interface";
import { testNotionConnection } from "./providers/notion";
import { testSlackConnection } from "./providers/slack";
import { testGoogleConnection } from "./providers/google";

export const TEST_FUNCTIONS: Record<string, TestOAuthConnectionFn> = {
  notion: testNotionConnection,
  slack: testSlackConnection,
  google: testGoogleConnection,
};
