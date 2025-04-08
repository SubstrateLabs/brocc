"use client";

import React, { useEffect, useState } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { useRouter, usePathname } from "next/navigation";

interface MdxAccordionGroupProps {
  children: React.ReactNode;
  defaultValue?: string; // To control which item is open by default
}

/**
 * Wrapper component for a group of accordion items.
 * Renders the main Shadcn Accordion component.
 */
export const MdxAccordionGroup: React.FC<MdxAccordionGroupProps> = ({
  children,
  defaultValue,
}) => {
  const [activeValue, setActiveValue] = useState<string | undefined>(
    defaultValue,
  );

  // Check URL hash on mount and when it changes
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace("#", "");
      if (hash) {
        setActiveValue(hash);
      }
    };

    // Initial check
    handleHashChange();

    // Listen for hash changes
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  return (
    <Accordion
      type="single"
      collapsible
      value={activeValue}
      onValueChange={(value) => {
        setActiveValue(value);
        if (value) {
          // Update URL hash without full page navigation
          window.history.pushState(null, "", `#${value}`);
        } else {
          // Remove hash when accordion is collapsed
          window.history.pushState(null, "", window.location.pathname);
        }
      }}
      className="w-full"
    >
      {children}
    </Accordion>
  );
};

interface MdxAccordionItemProps {
  value: string; // Unique value for this item
  title: string; // Title displayed in the trigger
  children: React.ReactNode; // Content of the accordion item
}

/**
 * Wrapper component for a single accordion item.
 * Renders Shadcn AccordionItem, AccordionTrigger, and AccordionContent.
 */
export const MdxAccordionItem: React.FC<MdxAccordionItemProps> = ({
  value,
  title,
  children,
}) => {
  return (
    <AccordionItem value={value} id={value}>
      <div className="relative">
        <div className="absolute inset-0 bg-[radial-gradient(#d1d5db_0.5px,transparent_0.5px)] bg-[length:4px_4px] opacity-50 rounded-lg" />
        <AccordionTrigger className="text-xl relative z-10">
          {title}
        </AccordionTrigger>
      </div>
      <AccordionContent className="text-lg">{children}</AccordionContent>
    </AccordionItem>
  );
};
