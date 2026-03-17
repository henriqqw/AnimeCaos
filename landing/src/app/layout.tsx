import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import { SITE_NAME, SITE_URL, SITE_X_HANDLE } from "@/lib/seo";
import "./globals.css";

const siteDescription =
  "AnimeCaos - Assistir animes sem anúncios, com player limpo, download offline e integração AniList.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_NAME,
    template: `%s | ${SITE_NAME}`,
  },
  description: siteDescription,
  keywords: ["animecaos", "AnimeCaos", "anime", "assistir anime", "download anime", "anime player", "ani-tupi", "animes online", "animes grátis", "player de animes", "anime desktop", "anime dublado", "anime legendado", "anime pt-br", "anime pt-br dublado", "anime pt-br legendado", "anime pt-br online", "anime pt-br grátis", "anime pt-br player", "anime pt-br desktop", "anime pt-br dublado", "anime pt-br legendado", "anime pt-br online", "anime pt-br grátis", "anime pt-br player", "anime pt-br desktop", "anime pt-br dublado", "anime pt-br legendado", "anime pt-br online", "anime pt-br grátis", "anime pt-br player", "anime pt-br desktop", "anime pt-br dublado", "anime pt-br legendado"],
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
    site: SITE_X_HANDLE,
    creator: SITE_X_HANDLE,
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
    <html lang="pt" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-TV4R97XS');`
          }}
        />
      </head>
      <body>
        <noscript>
          <iframe
            src="https://www.googletagmanager.com/ns.html?id=GTM-TV4R97XS"
            height="0"
            width="0"
            style={{ display: "none", visibility: "hidden" }}
          />
        </noscript>
        <script
          type="application/ld+json"
          // Basic WebSite schema for crawler understanding.
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteJsonLd) }}
        />
        {children}
        <Analytics />
      </body>
    </html>
  );
}
