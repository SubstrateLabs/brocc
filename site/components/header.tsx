"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { Button } from "./button";

type HeaderProps = {
  user: {
    id: string;
    [key: string]: unknown;
  } | null;
};

export function Header({ user }: HeaderProps) {
  const pathname = usePathname();
  const isOnHome = pathname === "/";
  const isOnFaq = pathname === "/faq";

  return (
    <header className="top-0 z-50 w-full flex justify-between items-center border-b border-gray-200 bg-background/80 backdrop-blur-sm relative">
      <div className="absolute inset-0 bg-[radial-gradient(#d1d5db_0.5px,transparent_0.5px)] bg-[length:4px_4px] opacity-50" />
      <div className="relative z-10">
        {!isOnHome && (
          <Link href="/">
            <Button variant="ghost">
              <Image
                src="/brocc.svg"
                alt="Broccoli"
                width={16}
                height={16}
                className="mr-1"
              />
              Brocc
            </Button>
          </Link>
        )}
      </div>

      <div className="flex items-center gap-2 relative z-10">
        {isOnFaq && (
          <div className="text-sm font-medium text-muted-foreground px-4">
            Frequently asked questions
          </div>
        )}
        {isOnHome && user && (
          <Link href="/dashboard">
            <Button variant="default">Dashboard</Button>
          </Link>
        )}
      </div>
    </header>
  );
}
