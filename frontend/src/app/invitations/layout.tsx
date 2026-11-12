import { AppShell } from "@/components/app-shell";

// The signed-in app gets the sidebar; the public landing page does not.
export default function Layout({ children }: LayoutProps<"/invitations">) {
  return <AppShell>{children}</AppShell>;
}
