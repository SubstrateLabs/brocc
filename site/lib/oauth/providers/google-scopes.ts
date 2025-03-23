import { type ScopeInfo } from "../provider-interface";

export enum GoogleScopeCategory {
  Profile = "profile",
  Sheets = "sheets",
  Docs = "docs",
}

/**
 * https://developers.google.com/identity/protocols/oauth2/scopes
 */
export const GoogleScopes: Record<string, ScopeInfo> = {
  // Standard profile info – do not describe
  openid: { category: GoogleScopeCategory.Profile },
  profile: { category: GoogleScopeCategory.Profile },
  email: { category: GoogleScopeCategory.Profile },
  /**
   * These are "sensitive" (not "restricted") scopes.
   * Add here: https://console.cloud.google.com/auth/scopes?inv=1&invt=Abrx4g&project=broccolink-453420
   */
  "https://www.googleapis.com/auth/spreadsheets.readonly": {
    description: "View Sheets",
    category: GoogleScopeCategory.Sheets,
  },
  "https://www.googleapis.com/auth/documents.readonly": {
    description: "View Docs",
    category: GoogleScopeCategory.Docs,
  },
};
