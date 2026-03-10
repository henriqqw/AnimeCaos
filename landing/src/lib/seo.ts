import type { Metadata } from "next";

export type AppLocale = "pt" | "en";

export const SITE_URL = "https://animecaos.vercel.app";
export const SITE_NAME = "AnimeCaos";
const SOCIAL_IMAGE_URL = `${SITE_URL}/icon.png`;

const OPEN_GRAPH_LOCALE: Record<AppLocale, string> = {
  pt: "pt_BR",
  en: "en_US",
};

function normalizePathname(pathname = ""): string {
  if (!pathname) return "";
  return pathname.startsWith("/") ? pathname : `/${pathname}`;
}

export function toAppLocale(locale: string): AppLocale {
  return locale === "en" ? "en" : "pt";
}

export function buildLocalizedMetadata({
  locale,
  pathname = "",
  title,
  description,
}: {
  locale: AppLocale;
  pathname?: string;
  title: string;
  description: string;
}): Metadata {
  const path = normalizePathname(pathname);
  const canonical = `${SITE_URL}/${locale}${path}`;

  return {
    title,
    description,
    alternates: {
      canonical,
      languages: {
        pt: `${SITE_URL}/pt${path}`,
        en: `${SITE_URL}/en${path}`,
      },
    },
    openGraph: {
      title,
      description,
      url: canonical,
      siteName: SITE_NAME,
      type: "website",
      locale: OPEN_GRAPH_LOCALE[locale],
      alternateLocale: [locale === "pt" ? OPEN_GRAPH_LOCALE.en : OPEN_GRAPH_LOCALE.pt],
      images: [{ url: SOCIAL_IMAGE_URL, alt: SITE_NAME }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [SOCIAL_IMAGE_URL],
    },
  };
}
