import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

// Public pages are open to every crawler, AI crawlers included; workspaces are private.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: ["/", "/llms.txt"],
      disallow: ["/w/", "/workspaces", "/invitations", "/callback", "/sign-in", "/integrations/"],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
