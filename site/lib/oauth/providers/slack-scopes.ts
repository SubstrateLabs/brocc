import { type ScopeInfo } from "../provider-interface";

export enum SlackScopeCategory {
  MessageInfo = "message_info", // e.g. bookmarks, pins, urls
  PublicMessages = "public_messages",
}

/**
 * https://api.slack.com/scopes?filter=user
 */
export const SlackScopes: Record<string, ScopeInfo> = {
  /**
   * Note: User permissions (not Bot or Legacy bot)
   * https://api.slack.com/apps/A0834UYR7CK/oauth
   */
  "channels:history": {
    description: "View public channel messages",
    category: SlackScopeCategory.PublicMessages,
  },
  "channels:read": {
    description: "View public channel info",
    category: SlackScopeCategory.PublicMessages,
  },
  "bookmarks:read": {
    description: "View bookmarks",
    category: SlackScopeCategory.MessageInfo,
  },
  "links:read": {
    description: "View URLs in messages",
    category: SlackScopeCategory.MessageInfo,
  },
  "pins:read": {
    description: "View pinned messages",
    category: SlackScopeCategory.MessageInfo,
  },
};
