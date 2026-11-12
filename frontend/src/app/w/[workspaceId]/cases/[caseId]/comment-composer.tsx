"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import { useFormStatus } from "react-dom";

import { inputClass } from "@/components/action-form";
import { Button } from "@/components/ui/button";
import type { ActionState } from "@/lib/action-state";
import { cn } from "@/lib/utils";

type Member = { user_id: string; name: string };

function Submit() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" size="sm" disabled={pending}>
      {pending ? "Posting…" : "Comment"}
    </Button>
  );
}

/** Plain textarea with "@" suggestions; only mentions still present in the text are sent. */
export function CommentComposer({
  action,
  members,
}: {
  action: (state: ActionState, fd: FormData) => Promise<ActionState>;
  members: Member[];
}) {
  const [state, formAction] = useActionState(action, {});
  const [body, setBody] = useState("");
  const [picked, setPicked] = useState<Member[]>([]);
  const [query, setQuery] = useState<string | null>(null);
  const [active, setActive] = useState(0);
  const ref = useRef<HTMLTextAreaElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (!state.error && formRef.current?.dataset.submitted) {
      setBody("");
      setPicked([]);
      delete formRef.current.dataset.submitted;
    }
  }, [state]);

  const suggestions =
    query === null
      ? []
      : members.filter((m) => m.name.toLowerCase().includes(query.toLowerCase())).slice(0, 6);

  function onChange(value: string) {
    setBody(value);
    const caret = ref.current?.selectionStart ?? value.length;
    const match = /(?:^|\s)@([^\s@]{0,40})$/.exec(value.slice(0, caret));
    setQuery(match ? match[1] : null);
    setActive(0);
  }

  function choose(member: Member) {
    const caret = ref.current?.selectionStart ?? body.length;
    const before = body.slice(0, caret).replace(/@([^\s@]{0,40})$/, `@${member.name} `);
    setBody(before + body.slice(caret));
    setPicked((p) => (p.some((x) => x.user_id === member.user_id) ? p : [...p, member]));
    setQuery(null);
    requestAnimationFrame(() => ref.current?.focus());
  }

  const mentioned = picked.filter((m) => body.includes(`@${m.name}`));

  return (
    <form
      ref={formRef}
      action={(fd) => {
        formRef.current!.dataset.submitted = "1";
        return formAction(fd);
      }}
      className="relative flex flex-col gap-2"
    >
      <label htmlFor="comment-body" className="sr-only">
        Comment
      </label>
      <textarea
        id="comment-body"
        ref={ref}
        name="body"
        required
        maxLength={5000}
        rows={3}
        value={body}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (!suggestions.length) return;
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            setActive(
              (i) =>
                (i + (e.key === "ArrowDown" ? 1 : -1) + suggestions.length) % suggestions.length,
            );
          } else if (e.key === "Enter" || e.key === "Tab") {
            e.preventDefault();
            choose(suggestions[active]);
          } else if (e.key === "Escape") {
            setQuery(null);
          }
        }}
        placeholder="Add a note for the people on this case. Type @ to mention someone."
        className={cn(inputClass, "h-auto resize-y py-2")}
        aria-autocomplete="list"
        aria-controls="mention-suggestions"
      />
      {suggestions.length > 0 ? (
        <ul
          id="mention-suggestions"
          role="listbox"
          className="bg-popover absolute top-full z-10 mt-1 w-64 overflow-hidden rounded-md border text-sm shadow-md"
        >
          {suggestions.map((m, i) => (
            <li
              key={m.user_id}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                choose(m);
              }}
              className={cn("cursor-pointer px-3 py-1.5", i === active && "bg-muted")}
            >
              {m.name}
            </li>
          ))}
        </ul>
      ) : null}
      {mentioned.map((m) => (
        <input key={m.user_id} type="hidden" name="mention_user_ids" value={m.user_id} />
      ))}
      <div className="flex items-center justify-between gap-2">
        <span className="text-muted-foreground text-xs">
          {mentioned.length
            ? `Notifies ${mentioned.map((m) => m.name).join(", ")}`
            : "Comments are visible to everyone in the workspace."}
        </span>
        <Submit />
      </div>
      {state.error ? (
        <p role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
      ) : null}
    </form>
  );
}
