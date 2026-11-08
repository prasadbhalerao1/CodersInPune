import { authkitProxy } from "@workos-inc/authkit-nextjs";

// Session management for every page. Pages are protected by default; only the landing
// page and the auth routes are reachable without a session.
export default authkitProxy({
  middlewareAuth: {
    enabled: true,
    unauthenticatedPaths: ["/", "/sign-in", "/callback"],
  },
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
