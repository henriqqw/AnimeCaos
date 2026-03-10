import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import PageWrapper from "@/components/layout/PageWrapper";
import AboutContent from "@/components/sections/AboutContent";
import { buildLocalizedMetadata, toAppLocale } from "@/lib/seo";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
    const locale = toAppLocale((await params).locale);
    const t = await getTranslations({ locale, namespace: "about" });

    return buildLocalizedMetadata({
        locale,
        pathname: "/about",
        title: locale === "pt" ? "Sobre o AnimeCaos" : "About AnimeCaos",
        description: t("p1"),
    });
}

export default async function AboutPage({ params }: { params: Promise<{ locale: string }> }) {
    const { locale } = await params;
    return (
        <PageWrapper locale={locale}>
            <AboutContent />
        </PageWrapper>
    );
}
