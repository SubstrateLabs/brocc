/**
 * Copies root README.md to site/markdown/readme.mdx and transforms <details> tags to use MdxAccordion components.
 */

import fs from 'fs';
import path from 'path';

// --- Configuration ---
const rootDir = path.resolve(__dirname, '../../');
const sourceFile = path.join(rootDir, 'README.md');
const targetDir = path.join(__dirname, '../markdown');
const targetFile = path.join(targetDir, 'readme.mdx');
const accordionImport = 'import { MdxAccordionGroup, MdxAccordionItem } from "@/components/mdx/Accordion";\n';
const codeBlockImport = 'import { CodeBlock, InlineCode } from "@/components/mdx/CodeBlock";\n\n';

// --- Helper Functions ---
/** Extracts the title from <h2> tags within <summary> */
const getTitle = (summaryTag: string): string => {
  const match = summaryTag.match(/<h2>(.*?)<\/h2>/);
  return match ? match[1].trim() : 'Untitled';
};

/** Creates a URL-friendly value from a title */
const getValue = (title: string): string => {
  return title.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
};

// --- Main Logic ---
// Make sure target directory exists
if (!fs.existsSync(targetDir)) {
  fs.mkdirSync(targetDir, { recursive: true });
}

try {
  // Read the source file
  let content = fs.readFileSync(sourceFile, 'utf8');

  // 1. Add the import statements
  content = accordionImport + codeBlockImport + content;

  // 2. Find the first <details open> and determine defaultValue
  let defaultValue = '';
  const firstOpenDetailsMatch = content.match(/<details\s+open>\s*<summary>([\s\S]*?)<\/summary>/);
  if (firstOpenDetailsMatch && firstOpenDetailsMatch[1]) {
    const firstTitle = getTitle(firstOpenDetailsMatch[1]);
    defaultValue = getValue(firstTitle);
  }

  // 3. Wrap everything in MdxAccordionGroup
  content = content.replace(
    /(<details[\s\S]*?<\/details>)/, // Find the first details block
    `<MdxAccordionGroup${defaultValue ? ` defaultValue="${defaultValue}"` : ''}>\n$1` // Add opening group tag before it
  );
  content = content.replace(
    /(<\/details>)(?![\s\S]*<\/details>)/, // Find the last closing details tag
    `$1\n</MdxAccordionGroup>` // Add closing group tag after it
  );


  // 4. Replace all <details>, <summary>, and </details>
  content = content.replace(/<details.*?>\s*<summary>(.*?)<\/summary>\s*([\s\S]*?)\s*<\/details>/g, (match, summaryContent, detailsContent) => {
    const title = getTitle(summaryContent);
    const value = getValue(title);
    // Remove leading/trailing whitespace from content block that might be left from summary removal
    const cleanedDetailsContent = detailsContent.trim(); 
    return `<MdxAccordionItem title="${title}" value="${value}">\n${cleanedDetailsContent}\n</MdxAccordionItem>`;
  });

  // 5. Replace code blocks with CodeBlock component
  content = content.replace(/```(\w+)?\n([\s\S]*?)\n```/gm, (match, language, code) => {
    // Escape backticks and curly braces in the code
    const escapedCode = code.replace(/`/g, '\\`').replace(/{/g, '\\{').replace(/}/g, '\\}');
    const languageProp = language ? ` language="${language}"` : '';
    return `<CodeBlock${languageProp} code={\`${escapedCode}\`} />`;
  });

  // 6. Replace inline code tags with InlineCode component
  content = content.replace(/`([^`]+)`/g, (match, code) => {
    // Escape backticks and curly braces in the code
    const escapedCode = code.replace(/`/g, '\\`').replace(/{/g, '\\{').replace(/}/g, '\\}');
    return `<InlineCode code={\`${escapedCode}\`} />`;
  });

  // Write the transformed content to the target file
  fs.writeFileSync(targetFile, content);

  console.log(`Successfully copied and transformed README.md from ${sourceFile} to ${targetFile}`);
} catch (error) {
  console.error('Error copying/transforming README.md:', error);
  // Only exit with error code in development, not in CI environments
  if (!process.env.CI && !process.env.VERCEL) {
    process.exit(1);
  } else {
    console.log('Running in CI environment, continuing despite error');
  }
}
