import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/seo";

const ROUTES = [
  "",
  "/pt",
  "/en",
  "/pt/about",
  "/pt/download",
  "/pt/how-to-use",
  "/pt/contact",
  "/en/about",
  "/en/download",
  "/en/how-to-use",
  "/en/contact",
];

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  return ROUTES.map((route) => ({
    url: `${SITE_URL}${route}`,
    lastModified,
  }));
}
