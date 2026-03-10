import type { Metadata } from "next";
import Script from "next/script";
import PageWrapper from "@/components/layout/PageWrapper";
import DownloadContent from "@/components/sections/DownloadContent";
import { buildLocalizedMetadata, toAppLocale } from "@/lib/seo";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
    const locale = toAppLocale((await params).locale);
    const isPt = locale === "pt";

    return buildLocalizedMetadata({
        locale,
        pathname: "/download",
        title: isPt ? "Download do AnimeCaos" : "AnimeCaos Download",
        description: isPt
            ? "Baixe o AnimeCaos para Windows em um pacote unico, sem dependencias extras."
            : "Download AnimeCaos for Windows in one package with no extra dependencies.",
    });
}

const softwareJsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "AnimeCaos",
    operatingSystem: "Windows",
    applicationCategory: "MultimediaApplication",
    softwareVersion: "0.1.0",
    downloadUrl: "https://github.com/henriqqw/animecaos/releases/download/v0.1.0/AnimeCaos.v0.1.0.-.Official.Release.zip",
    offers: { "@type": "Offer", price: "0", priceCurrency: "BRL" },
    description: "Hub de anime desktop open source. Player limpo, download offline, integracao AniList.",
    publisher: { "@type": "Organization", name: "caosdev", url: "https://caosdev.vercel.app" },
};

export default async function DownloadPage({ params }: { params: Promise<{ locale: string }> }) {
    const { locale } = await params;
    return (
        <PageWrapper locale={locale}>
            <Script
                id="software-ld"
                type="application/ld+json"
                dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareJsonLd) }}
            />
            <DownloadContent />
        </PageWrapper>
    );
}
