"use client";

import { Menu, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { SidebarNav } from "./SidebarNav";

export function MobileNav({ brand }: { brand: React.ReactNode }) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [prevPathname, setPrevPathname] = useState(pathname);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  if (prevPathname !== pathname) {
    setPrevPathname(pathname);
    setOpen(false);
  }

  useEffect(() => {
    if (!open) {
      return;
    }
    closeButtonRef.current?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-expanded={open}
        aria-haspopup="dialog"
        className="flex size-11 items-center justify-center rounded-md text-ink outline-none transition-colors duration-200 hover:bg-cloud focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        <Menu aria-hidden className="size-6" />
        <span className="sr-only">{t("openMenu")}</span>
      </button>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            role="presentation"
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-ink/40 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-200"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label={t("menu")}
            className="absolute inset-y-0 start-0 flex w-72 max-w-[85vw] flex-col gap-6 overflow-y-auto bg-canvas p-6 shadow-floating-modal motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-200"
          >
            <div className="flex items-center justify-between">
              {brand}
              <button
                ref={closeButtonRef}
                type="button"
                onClick={() => setOpen(false)}
                className="flex size-11 items-center justify-center rounded-md text-ink outline-none transition-colors duration-200 hover:bg-cloud focus-visible:ring-2 focus-visible:ring-ring/50"
              >
                <X aria-hidden className="size-6" />
                <span className="sr-only">{t("closeMenu")}</span>
              </button>
            </div>
            <SidebarNav onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}
    </>
  );
}
