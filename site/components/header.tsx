"use client";

import Link from "next/link";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { usePathname } from "next/navigation";

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
    <header className="w-full flex justify-between items-center border-b border-border p-2">
      <div>
        <Link href="/">
          <Button variant="outline" size="sm" className="border-0 shadow-none font-mono" style={{ fontFamily: 'Berkeley Mono Variable, monospace' }}>
            <Image src="/brocc.svg" alt="Broccoli" width={16} height={16} className="" />
            brocc.
          </Button>
        </Link>
      </div>

      <div className="flex items-center gap-2 font-mono" style={{ fontFamily: 'Berkeley Mono Variable, monospace' }}>
        {isOnHome && !user && (
          <Link href={signInUrl}>
            <Button variant="outline" size="sm">
              Sign in
            </Button>
          </Link>
        )}
        {isOnHome && user && (
          <Link href="/dashboard">
            <Button variant="outline" size="sm">
              Dashboard
            </Button>
          </Link>
        )}
      </div>
    </header>
  );
}
