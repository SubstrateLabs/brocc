"use client";

import Link from "next/link";
import { SiGithub } from "@icons-pack/react-simple-icons";

export function Footer() {
  return (
    <footer className="w-full py-4 border-t border-gray-200 relative">
      <div className="absolute inset-0 bg-[radial-gradient(#d1d5db_0.5px,transparent_0.5px)] bg-[length:4px_4px] opacity-50" />
      <div className="container mx-auto flex justify-center items-center relative z-10">
        <Link 
          href="https://github.com/substratelabs/brocc"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <SiGithub size={16} />
          <span>github.com/substratelabs/brocc</span>
        </Link>
      </div>
    </footer>
  );
}
