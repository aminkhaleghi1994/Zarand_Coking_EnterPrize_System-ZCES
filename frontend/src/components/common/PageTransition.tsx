"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div
      key={pathname}
      className="motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-2 motion-safe:duration-200"
    >
      {children}
    </div>
  );
}
