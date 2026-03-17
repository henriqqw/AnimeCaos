import type { Metadata } from "next";
import { permanentRedirect } from "next/navigation";
import { SITE_NAME, SITE_URL, SITE_X_HANDLE } from "@/lib/seo";

const rootDescription =
  "Choose Portuguese or English to explore AnimeCaos: an open source anime desktop hub with clean playback and offline downloads.";

export const metadata: Metadata = {
  title: SITE_NAME,
  description: rootDescription,
  alternates: {
    canonical: SITE_URL,
    languages: {
      en: `${SITE_URL}/en`,
      pt: `${SITE_URL}/pt`,
      "x-default": `${SITE_URL}/pt`,
    },
  },
  openGraph: {
    title: SITE_NAME,
    description: rootDescription,
    url: SITE_URL,
    siteName: SITE_NAME,
    type: "website",
    images: [{ url: `${SITE_URL}/icon.png`, alt: SITE_NAME }],
  },
  twitter: {
    card: "summary_large_image",
    site: SITE_X_HANDLE,
    creator: SITE_X_HANDLE,
    title: SITE_NAME,
    description: rootDescription,
    images: [`${SITE_URL}/icon.png`],
  },
};

export default function RootPage() {
  permanentRedirect("/pt");
}
