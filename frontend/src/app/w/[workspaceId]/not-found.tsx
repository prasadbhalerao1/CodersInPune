import { ErrorScreen } from "@/components/error-screen";

// Shown for anything the API reports as missing, including workspaces the person is not a
// member of: Relay never distinguishes "doesn't exist" from "not yours".
export default function NotFound() {
  return (
    <ErrorScreen
      code="404"
      title="Not found"
      home={{ href: "/workspaces", label: "Your workspaces" }}
    >
      It doesn&apos;t exist, or you don&apos;t have access to it. Ask a workspace admin if you think
      you should.
    </ErrorScreen>
  );
}
