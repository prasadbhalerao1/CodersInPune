// Re-mounts on every navigation inside a workspace, so each page eases in.
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="motion-page flex flex-1 flex-col">{children}</div>;
}
