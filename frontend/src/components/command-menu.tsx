"use client";

import { useParams, useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useTransition,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import { inputClass } from "@/components/action-form";
import { Button } from "@/components/ui/button";
import { useWorkspaceContext } from "@/components/workspace-context";
import {
  quickCreateAction,
  searchAction,
  type QuickCreateKind,
} from "@/app/w/[workspaceId]/command-actions";
import { ASSET_TYPE_LABEL, ASSET_TYPES } from "@/app/w/[workspaceId]/assets/labels";
import { hitPath, KIND_GROUP } from "@/lib/search";
import type { SearchHit, WorkspaceRole } from "@/lib/types";
import { cn } from "@/lib/utils";

export const OPEN_COMMAND_MENU = "relay:open-command-menu";

type Item = {
  key: string;
  group: string;
  label: string;
  detail?: string | null;
  keywords?: string;
  path?: string;
  create?: QuickCreateKind;
};

const RECENT_KEY = "relay:recent-searches";
function readRecent(): string[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]") as string[];
  } catch {
    return [];
  }
}
function remember(q: string) {
  try {
    const next = [q, ...readRecent().filter((r) => r !== q)].slice(0, 5);
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable: recent searches are a convenience */
  }
}

const MANAGE: readonly WorkspaceRole[] = ["owner", "admin"];
const WRITE: readonly WorkspaceRole[] = ["owner", "admin", "member"];

/** Cmd/Ctrl+K: search everything, jump anywhere, create the common records. */
export function CommandMenu() {
  const { workspaceId } = useParams<{ workspaceId?: string }>();
  const context = useWorkspaceContext();
  const role = context && context.workspaceId === workspaceId ? context.role : null;
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [searching, startSearch] = useTransition();
  const [active, setActive] = useState(0);
  const [creating, setCreating] = useState<QuickCreateKind | null>(null);
  const [recent, setRecent] = useState<string[]>([]);

  const open = useCallback(() => {
    if (!workspaceId) return;
    setCreating(null);
    setRecent(readRecent());
    dialog.current?.showModal();
    requestAnimationFrame(() => input.current?.select());
  }, [workspaceId]);
  const close = useCallback(() => dialog.current?.close(), []);

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (dialog.current?.open) close();
        else open();
      }
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_COMMAND_MENU, open);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(OPEN_COMMAND_MENU, open);
    };
  }, [open, close]);

  // Debounced, permission-aware search (the API applies each module's visibility rules).
  useEffect(() => {
    if (!workspaceId) return;
    const q = query.trim();
    if (q.length < 2) return;
    const timer = setTimeout(() => {
      startSearch(async () => {
        const result = await searchAction(workspaceId, q);
        setHits(result.hits);
        setActive(0);
      });
    }, 150);
    return () => clearTimeout(timer);
  }, [query, workspaceId]);

  const go = useCallback(
    (path: string) => {
      if (query.trim().length >= 2) remember(query.trim());
      close();
      router.push(`/w/${workspaceId}${path}`);
    },
    [close, query, router, workspaceId],
  );

  const items = useMemo<Item[]>(() => {
    const can = (roles: readonly WorkspaceRole[]) => role !== null && roles.includes(role);
    const shown = query.trim().length >= 2 ? hits : [];
    const results: Item[] = shown.map((hit) => ({
      key: `${hit.kind}:${hit.id}:${hit.title}`,
      group: KIND_GROUP[hit.kind],
      label: hit.title,
      detail: [hit.detail, hit.status && hit.status !== "active" ? hit.status : null]
        .filter(Boolean)
        .join(" · "),
      path: hitPath(hit),
    }));
    if (shown.length) {
      results.push({
        key: "all-results",
        group: "Search",
        label: `See all results for “${query.trim()}”`,
        path: `/search?q=${encodeURIComponent(query.trim())}`,
      });
    }
    const create: Item[] = [
      ...(can(MANAGE)
        ? [
            { key: "c-resp", label: "New responsibility", path: "/responsibilities/new" },
            {
              key: "c-transfer",
              label: "New transfer case",
              keywords: "continuity handover",
              path: "/cases/new?type=transfer",
            },
            {
              key: "c-coverage",
              label: "New temporary coverage case",
              keywords: "continuity leave absence",
              path: "/cases/new?type=coverage",
            },
            {
              key: "c-departure",
              label: "New departure case",
              keywords: "continuity leaving offboarding",
              path: "/cases/new?type=departure",
            },
            { key: "c-person", label: "Add person", create: "person" as const },
            { key: "c-team", label: "Add team", create: "team" as const },
            { key: "c-dept", label: "Add department", create: "department" as const },
            { key: "c-asset", label: "Add asset", create: "asset" as const },
          ]
        : []),
      ...(can(WRITE)
        ? [
            {
              key: "c-knowledge",
              label: "Add knowledge",
              detail: "Pick the responsibility it belongs to",
              path: "/knowledge?add=1",
            },
          ]
        : []),
    ].map((i) => ({ ...i, group: "Create" }));
    const navigate: Item[] = [
      ["My Work", "/my-work"],
      ["Inbox", "/inbox"],
      ["Continuity cases", "/cases"],
      ["Responsibilities", "/responsibilities"],
      ["People & Teams", "/people"],
      ["Knowledge", "/knowledge"],
      ["Risks", "/risks"],
      ...(can([...MANAGE, "auditor"]) ? [["Insights", "/insights"]] : []),
      ...(can(MANAGE)
        ? [
            ["Integrations", "/integrations"],
            ["Automations", "/automations"],
            ["Agents", "/agents"],
          ]
        : []),
      ["Settings", "/settings"],
    ].map(([label, path]) => ({
      key: `n-${path}`,
      group: "Go to",
      label: `Open ${label}`,
      path,
    }));
    const q = query.trim().toLowerCase();
    const matches = (i: Item) => !q || `${i.label} ${i.keywords ?? ""}`.toLowerCase().includes(q);
    return [...results, ...create.filter(matches), ...navigate.filter(matches)];
  }, [hits, query, role]);

  const runItem = (item: Item) => {
    if (item.create) setCreating(item.create);
    else if (item.path) go(item.path);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = items[active];
      if (item) runItem(item);
    }
  };

  useEffect(() => {
    document.getElementById(`cmd-item-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!workspaceId) return null;
  let lastGroup = "";

  return (
    <dialog
      ref={dialog}
      aria-label="Search and commands"
      onClose={() => {
        setQuery("");
        setHits([]);
        setCreating(null);
      }}
      onClick={(e) => e.target === dialog.current && close()}
      className="bg-background text-foreground m-auto mt-[12vh] w-[min(40rem,calc(100vw-2rem))] rounded-xl border p-0 shadow-2xl backdrop:bg-black/30"
    >
      {creating ? (
        <QuickCreate
          workspaceId={workspaceId}
          kind={creating}
          onBack={() => {
            setCreating(null);
            requestAnimationFrame(() => input.current?.focus());
          }}
          onCreated={(path) => go(path)}
        />
      ) : (
        <>
          <div className="flex items-center gap-2 border-b px-4">
            <span aria-hidden className="text-muted-foreground text-sm">
              ⌕
            </span>
            <input
              ref={input}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Search people, responsibilities, cases, knowledge… or type a command"
              aria-label="Search or type a command"
              role="combobox"
              aria-expanded="true"
              aria-controls="cmd-list"
              aria-activedescendant={items.length ? `cmd-item-${active}` : undefined}
              className="h-12 flex-1 bg-transparent text-sm outline-none"
            />
            {searching ? <span className="text-muted-foreground text-xs">Searching…</span> : null}
            <kbd className="text-muted-foreground rounded border px-1.5 text-[10px]">Esc</kbd>
          </div>
          <ul id="cmd-list" role="listbox" className="max-h-[60vh] overflow-y-auto p-2">
            {!query && recent.length ? (
              <li className="px-2 pt-1 pb-2 text-xs">
                <span className="text-muted-foreground mr-2">Recent:</span>
                {recent.map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setQuery(r)}
                    className="hover:bg-muted mr-1 rounded border px-1.5 py-0.5"
                  >
                    {r}
                  </button>
                ))}
              </li>
            ) : null}
            {query.trim().length >= 2 && !searching && hits.length === 0 ? (
              <li className="text-muted-foreground px-2 py-3 text-sm">
                No records match “{query.trim()}”. You only see what your role can access.
              </li>
            ) : null}
            {items.map((item, index) => {
              const heading = item.group !== lastGroup ? item.group : null;
              lastGroup = item.group;
              return (
                <li key={item.key} role="presentation">
                  {heading ? (
                    <p className="text-muted-foreground px-2 pt-3 pb-1 text-[11px] font-medium tracking-wide uppercase">
                      {heading}
                    </p>
                  ) : null}
                  <div
                    id={`cmd-item-${index}`}
                    role="option"
                    aria-selected={index === active}
                    onMouseMove={() => setActive(index)}
                    onClick={() => runItem(item)}
                    className={cn(
                      "flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 text-sm",
                      index === active && "bg-foreground/[0.06]",
                    )}
                  >
                    <span className="min-w-0 flex-1 truncate">{item.label}</span>
                    {item.detail ? (
                      <span className="text-muted-foreground max-w-[45%] truncate text-xs">
                        {item.detail}
                      </span>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
          <p className="text-muted-foreground border-t px-4 py-2 text-[11px]">
            ↑↓ to move · Enter to open · Esc to close
          </p>
        </>
      )}
    </dialog>
  );
}

const CREATE_LABEL: Record<QuickCreateKind, string> = {
  person: "Add person",
  team: "Add team",
  department: "Add department",
  asset: "Add asset",
};
const CREATED_PATH: Record<QuickCreateKind, (id: string) => string> = {
  person: (id) => `/people/${id}`,
  team: (id) => `/teams/${id}`,
  department: (id) => `/departments/${id}`,
  asset: (id) => `/assets/${id}`,
};

function QuickCreate({
  workspaceId,
  kind,
  onBack,
  onCreated,
}: {
  workspaceId: string;
  kind: QuickCreateKind;
  onBack: () => void;
  onCreated: (path: string) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    startTransition(async () => {
      const result = await quickCreateAction(workspaceId, kind, fd);
      if (result.id) onCreated(CREATED_PATH[kind](result.id));
      else setError(result.error ?? "Couldn't create it. Try again.");
    });
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-3 p-4" aria-label={CREATE_LABEL[kind]}>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onBack}
          className="text-muted-foreground hover:text-foreground text-sm"
          aria-label="Back to commands"
        >
          ←
        </button>
        <h2 className="text-sm font-semibold">{CREATE_LABEL[kind]}</h2>
      </div>
      <label className="flex flex-col gap-1 text-sm">
        Name
        <input name="name" required maxLength={200} autoFocus className={inputClass} />
      </label>
      {kind === "person" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            Email (optional)
            <input name="email" type="email" className={inputClass} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Title (optional)
            <input name="title" maxLength={200} className={inputClass} />
          </label>
        </div>
      ) : null}
      {kind === "asset" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            Type
            <select name="asset_type" defaultValue="service" className={inputClass}>
              {ASSET_TYPES.map((t) => (
                <option key={t} value={t}>
                  {ASSET_TYPE_LABEL[t]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Link (optional)
            <input name="url" type="url" pattern="https?://.+" className={inputClass} />
          </label>
        </div>
      ) : null}
      {error ? (
        <p role="alert" className="text-destructive text-sm">
          {error}
        </p>
      ) : null}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onBack}>
          Cancel
        </Button>
        <Button type="submit" size="sm" disabled={pending}>
          {pending ? "Creating…" : "Create"}
        </Button>
      </div>
    </form>
  );
}

/** Sidebar entry point for people who don't use the shortcut. */
export function CommandTrigger() {
  const { workspaceId } = useParams<{ workspaceId?: string }>();
  if (!workspaceId) return null;
  return (
    <div className="px-3 pt-3">
      <button
        type="button"
        onClick={() => window.dispatchEvent(new Event(OPEN_COMMAND_MENU))}
        data-tour="search"
        className="text-muted-foreground hover:text-foreground hover:bg-muted flex w-full items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm"
      >
        <span aria-hidden>⌕</span>
        <span className="flex-1 text-left">Search or create…</span>
        <kbd className="rounded border px-1 text-[10px]">Ctrl K</kbd>
      </button>
    </div>
  );
}

/** Phone top bar: the sidebar (and its trigger) is hidden below md. */
export function MobileSearchButton() {
  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new Event(OPEN_COMMAND_MENU))}
      aria-label="Search or create"
      className="text-muted-foreground hover:text-foreground grid size-12 shrink-0 place-items-center border-l"
    >
      ⌕
    </button>
  );
}
