import { AccountConnection } from "@/lib/oauth/test-connections";
import { type OauthProvider } from "@/lib/oauth/types";

export function accountLabelForConnection(domain: OauthProvider, connection: AccountConnection) {
  if (domain === "notion") {
    if (!connection.providerMetadata) {
      return connection.account;
    }
    return `Workspace: ${connection.providerMetadata?.workspaceName}`;
  } else if (domain === "slack") {
    return `Team: ${connection.providerMetadata?.team}`;
  }
  return connection.account;
}
