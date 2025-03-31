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
  signInUrl: string;
};

export function Header({ user, signInUrl }: HeaderProps) {
  const pathname = usePathname();
  const isOnHome = pathname === "/";

  return (
    <header className="w-full flex justify-between items-center border-b border-gray-200">
      <div>
        {isOnHome ? (
          <div className="text-sm font-medium text-muted-foreground px-4">Know thyself</div>
        ) : (
          <Link href="/">
            <Button variant="ghost">
              <Image src="/brocc.svg" alt="Broccoli" width={16} height={16} className="mr-1" />
              Brocc
            </Button>
          </Link>
        )}
      </div>

      <div className="flex items-center gap-2">
        {isOnHome && !user && (
          <Link href={signInUrl}>
            <Button variant="default">Sign in</Button>
          </Link>
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
