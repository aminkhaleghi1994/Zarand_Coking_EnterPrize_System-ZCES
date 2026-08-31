"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { warehouseApi, type WarehouseItem } from "@/lib/client-api";
import { cn } from "@/lib/utils";

type Props = {
  onSelect: (item: WarehouseItem) => void;
  onClear?: () => void;
  selected?: WarehouseItem | null;
  invalid?: boolean;
};

/** Debounced (300ms) live item picker over the backend's indexed, paginated
 * search — the piece Phase 5's request lines will reuse (T021). */
export function ItemSearchCombobox({ onSelect, onClear, selected, invalid }: Props) {
  const t = useTranslations("warehouse.catalog");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    const onClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const results = useQuery({
    queryKey: ["warehouse-item-search", debounced],
    queryFn: ({ signal }) => warehouseApi.items.search(debounced, signal),
    enabled: open && debounced.length > 0,
  });

  const items = results.data?.ok ? results.data.data.items : [];

  return (
    <div ref={containerRef} className="relative">
      <Input
        type="search"
        role="combobox"
        aria-expanded={open}
        aria-controls="warehouse-item-search-results"
        aria-label={t("searchPlaceholder")}
        aria-invalid={invalid ? "true" : undefined}
        value={selected ? (selected.code ? `${selected.name} (${selected.code})` : selected.name) : search}
        onChange={(event) => {
          setSearch(event.target.value);
          setOpen(true);
          onClear?.();
        }}
        onFocus={() => setOpen(true)}
        placeholder={t("searchPlaceholder")}
        className={cn("h-11 w-full rounded-md", invalid && "border-bloom-deep")}
      />
      {selected ? (
        <button
          type="button"
          onClick={() => {
            onClear?.();
            setSearch("");
          }}
          className="absolute inset-y-0 end-2 my-auto h-8 rounded-md px-2 text-xs text-charcoal hover:bg-cloud"
        >
          {t("clearSelection")}
        </button>
      ) : null}
      {open && !selected ? (
        <div
          id="warehouse-item-search-results"
          role="listbox"
          className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-fog bg-canvas p-1 shadow-soft-lift"
        >
          {debounced.length === 0 ? (
            <p className="p-3 text-sm text-graphite">{t("searchHint")}</p>
          ) : results.isPending ? (
            <div className="grid gap-2 p-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : results.data?.ok && items.length > 0 ? (
            items.map((item) => (
              <button
                key={item.id}
                type="button"
                role="option"
                aria-selected="false"
                onClick={() => {
                  onSelect(item);
                  setOpen(false);
                }}
                className="flex h-11 w-full items-center justify-between rounded-md px-3 text-start text-sm outline-none transition-colors duration-200 hover:bg-cloud focus-visible:bg-cloud"
              >
                <span className="truncate">
                  {item.name}
                  {item.name_fa ? <span className="text-graphite"> · {item.name_fa}</span> : null}
                </span>
                <span className="ms-2 shrink-0 text-xs text-graphite">{item.code ?? "—"}</span>
              </button>
            ))
          ) : (
            <p className="p-3 text-sm text-graphite">{t("noResults")}</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
