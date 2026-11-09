/** The same "what Relay reads / never reads" statement on every integration page. */
export function DataScope({ reads, never }: { reads: string[]; never: string[] }) {
  return (
    <div className="grid gap-4 rounded-lg border p-4 text-sm sm:grid-cols-2">
      <div>
        <p className="mb-1 text-xs font-medium">Relay reads</p>
        <ul className="text-muted-foreground list-inside list-disc text-xs">
          {reads.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </div>
      <div>
        <p className="mb-1 text-xs font-medium">Relay never reads or writes</p>
        <ul className="text-muted-foreground list-inside list-disc text-xs">
          {never.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
