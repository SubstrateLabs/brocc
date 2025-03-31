"use client";

import React from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

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
  return (
    <Accordion type="single" collapsible defaultValue={defaultValue} className="w-full">
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
    <AccordionItem value={value}>
      <AccordionTrigger className="text-lg font-mono">{title}</AccordionTrigger>
      <AccordionContent>{children}</AccordionContent>
    </AccordionItem>
  );
}; 