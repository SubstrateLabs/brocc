import * as React from "react";
import * as SimpleIcons from "@icons-pack/react-simple-icons";
import "@/lib/string-extensions";
import { type OauthProvider } from "@/lib/oauth/types";

export function getProviderIcon(domain: OauthProvider): React.ReactElement | null {
  const iconName = `Si${domain.toTitleCase()}`;
  // @ts-expect-error - dynamic access
  const Icon = SimpleIcons[iconName];
  if (Icon) {
    return <Icon size={16} />;
  }
  return null;
}
