export default function HomePage() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="flex h-14 items-center border-b px-6">
        <h1 className="text-base font-semibold">Home</h1>
      </header>
      <section className="flex flex-1 items-center justify-center p-6">
        <div className="max-w-md text-center">
          <h2 className="text-lg font-semibold">Relay is being set up</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            Sign-in and workspace creation arrive in the next foundation slice.
          </p>
        </div>
      </section>
    </div>
  );
}
