import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/seo";

const LOCALES = ["pt", "en"] as const;
const ROUTES = ["", "/about", "/download", "/how-to-use", "/contact"] as const;

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  return LOCALES.flatMap((locale) =>
    ROUTES.map((route) => ({
      url: `${SITE_URL}/${locale}${route}`,
      lastModified,
      changeFrequency: route === "" ? "weekly" : "monthly",
      priority: route === "" ? 1 : 0.8,
      alternates: {
        languages: {
          "pt-BR": `${SITE_URL}/pt${route}`,
          "en-US": `${SITE_URL}/en${route}`,
        },
      },
    })),
  );
}
