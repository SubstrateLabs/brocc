import type { MDXComponents } from "mdx/types";
import { Checkbox } from "@/components/ui/checkbox";
import React from "react";

// Wrapper component for rendering checkboxes
const MdxCheckbox = (props: React.InputHTMLAttributes<HTMLInputElement>) => {
  // We render the Shadcn checkbox, passing the checked state
  // and explicitly disabling it as it's display-only in MDX.
  return <Checkbox checked={props.checked} disabled={true} />;
};

export function useMDXComponents(components: MDXComponents): MDXComponents {
  return {
    ...components,
    input: (props) => {
      if (props.type === "checkbox") {
        return <MdxCheckbox {...props} />;
      }
      return <input {...props} />;
    },
  };
}
