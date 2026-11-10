import { authkitProxy } from "@workos-inc/authkit-nextjs";

// Session management for every page. Pages are protected by default; only the landing
// page and the auth routes are reachable without a session.
export default authkitProxy({
  middlewareAuth: {
    enabled: true,
    // The GitHub webhook is authenticated by its HMAC signature (verified by the API).
    unauthenticatedPaths: ["/", "/sign-in", "/callback", "/integrations/github/webhook"],
  },
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
