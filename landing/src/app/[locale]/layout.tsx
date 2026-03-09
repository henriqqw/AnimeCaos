import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import Script from "next/script";
import "../globals.css";

export const metadata: Metadata = {
    metadataBase: new URL("https://animecaos.vercel.app"),
    title: {
        default: "AnimeCaos — Anime sem anúncio. Sem drama.",
        template: "%s | AnimeCaos",
    },
    description:
        "Hub desktop de anime open source. Pesquisa unificada, player limpo via mpv, download offline, integração AniList e Auto-Play. Windows, sem assinatura.",
    keywords: [
        "animecaos", "anime", "assistir anime", "download anime", "hub anime",
        "mpv", "yt-dlp", "open source", "windows", "sem anuncio", "offline",
    ],
    authors: [{ name: "caosdev", url: "https://caosdev.vercel.app" }],
    creator: "caosdev",
    openGraph: {
        type: "website",
        locale: "pt_BR",
        alternateLocale: "en_US",
        url: "https://animecaos.vercel.app",
        siteName: "AnimeCaos",
        title: "AnimeCaos — Anime sem anúncio. Sem drama.",
        description:
            "Hub desktop de anime open source. Pesquisa unificada, player limpo, download offline e integração AniList.",
        images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "AnimeCaos" }],
    },
    twitter: {
        card: "summary_large_image",
        title: "AnimeCaos — Anime sem anúncio. Sem drama.",
        description:
            "Hub desktop de anime open source. Pesquisa unificada, player limpo, download offline e integração AniList.",
        images: ["/og-image.png"],
        creator: "@chaosphory",
    },
    robots: { index: true, follow: true },
    alternates: {
        canonical: "https://animecaos.vercel.app",
        languages: {
            "pt-BR": "https://animecaos.vercel.app/pt",
            "en-US": "https://animecaos.vercel.app/en",
        },
    },
};

const locales = ["pt", "en"];

export default async function LocaleLayout({
    children,
    params,
}: {
    children: React.ReactNode;
    params: Promise<{ locale: string }>;
}) {
    const { locale } = await params;
    if (!locales.includes(locale)) notFound();
    const messages = await getMessages();

    return (
        <html lang={locale} suppressHydrationWarning>
            <head>
                <Script
                    id="organization-ld"
                    type="application/ld+json"
                    dangerouslySetInnerHTML={{
                        __html: JSON.stringify({
                            "@context": "https://schema.org",
                            "@graph": [
                                {
                                    "@type": "Organization",
                                    "@id": "https://animecaos.vercel.app/#organization",
                                    name: "AnimeCaos",
                                    url: "https://animecaos.vercel.app",
                                    logo: "https://animecaos.vercel.app/icon.png",
                                    sameAs: [
                                        "https://github.com/henriqqw/animecaos",
                                        "https://caosdev.vercel.app",
                                    ],
                                },
                                {
                                    "@type": "WebSite",
                                    "@id": "https://animecaos.vercel.app/#website",
                                    url: "https://animecaos.vercel.app",
                                    name: "AnimeCaos",
                                    description:
                                        "Hub desktop de anime open source — player limpo, download offline, integração AniList.",
                                    publisher: { "@id": "https://animecaos.vercel.app/#organization" },
                                    inLanguage: ["pt-BR", "en-US"],
                                    potentialAction: {
                                        "@type": "SearchAction",
                                        target: {
                                            "@type": "EntryPoint",
                                            urlTemplate:
                                                "https://github.com/henriqqw/animecaos/search?q={search_term_string}",
                                        },
                                        "query-input": "required name=search_term_string",
                                    },
                                },
                            ],
                        }),
                    }}
                />
            </head>
            <body>
                <NextIntlClientProvider messages={messages}>
                    <div className="grid-bg" aria-hidden="true" />
                    {children}
                </NextIntlClientProvider>
            </body>
        </html>
    );
}
