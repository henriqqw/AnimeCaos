import type { Metadata } from "next";
import { SITE_NAME, SITE_URL } from "@/lib/seo";
import "./globals.css";

const siteDescription =
  "Open source anime desktop hub with unified search, ad-free playback, offline downloads, and AniList integration.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_NAME,
    template: `%s | ${SITE_NAME}`,
  },
  description: siteDescription,
  robots: { index: true, follow: true },
  alternates: {
    canonical: SITE_URL,
    languages: {
      en: `${SITE_URL}/en`,
      pt: `${SITE_URL}/pt`,
    },
  },
  openGraph: {
    title: SITE_NAME,
    description: siteDescription,
    url: SITE_URL,
    siteName: SITE_NAME,
    type: "website",
    images: [{ url: `${SITE_URL}/icon.png`, alt: SITE_NAME }],
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_NAME,
    description: siteDescription,
    images: [`${SITE_URL}/icon.png`],
  },
  verification: {
    google: "aKSh1c77D7HrmDemHcz8n7BgG1RSW0yw934WFZDX87w",
  },
};

const websiteJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: SITE_NAME,
  url: SITE_URL,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt">
      <body>
        <script
          type="application/ld+json"
          // Basic WebSite schema for crawler understanding.
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
        />
        {children}
      </body>
    </html>
  );
}
