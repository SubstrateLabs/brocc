/**
 * Copies root README.md to site/markdown/readme.mdx
 */

import fs from 'fs';
import path from 'path';

// Get the absolute path to the root directory (one level up from site/)
const rootDir = path.resolve(__dirname, '../../');
const sourceFile = path.join(rootDir, 'README.md');
const targetDir = path.join(__dirname, '../markdown');
const targetFile = path.join(targetDir, 'readme.mdx');

// Make sure target directory exists
if (!fs.existsSync(targetDir)) {
  fs.mkdirSync(targetDir, { recursive: true });
}

try {
  // Read the source file
  const content = fs.readFileSync(sourceFile, 'utf8');
  
  // Write to the target file
  fs.writeFileSync(targetFile, content);
  
  console.log(`Successfully copied README.md from ${sourceFile} to ${targetFile}`);
} catch (error) {
  console.error('Error copying README.md:', error);
  // Only exit with error code in development, not in CI environments
  if (!process.env.CI && !process.env.VERCEL) {
    process.exit(1);
  } else {
    console.log('Running in CI environment, continuing despite error');
  }
}
