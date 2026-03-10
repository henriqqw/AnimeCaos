import Link from "next/link";
import type { Metadata } from "next";
import { SITE_NAME, SITE_URL } from "@/lib/seo";

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
      "x-default": SITE_URL,
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
    title: SITE_NAME,
    description: rootDescription,
    images: [`${SITE_URL}/icon.png`],
  },
};

export default function RootPage() {
  return (
    <main
      style={{
        minHeight: "100dvh",
        display: "grid",
        placeItems: "center",
        padding: "1.5rem",
      }}
    >
      <section
        className="liquid-glass"
        style={{ maxWidth: 680, width: "100%", padding: "2rem", zIndex: 1 }}
      >
        <h1 className="heading-lg" style={{ marginBottom: "0.75rem" }}>
          AnimeCaos
        </h1>
        <p className="text-muted" style={{ marginBottom: "1.5rem", lineHeight: 1.65 }}>
          Select your language to continue.
        </p>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <Link href="/pt" className="btn btn-primary">
            Portuguese (PT)
          </Link>
          <Link href="/en" className="btn btn-ghost">
            English
          </Link>
        </div>
      </section>
    </main>
  );
}
