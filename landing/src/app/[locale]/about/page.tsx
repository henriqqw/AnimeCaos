import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { motion } from "framer-motion";
import PageWrapper from "@/components/layout/PageWrapper";
import AboutContent from "@/components/sections/AboutContent";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
    const { locale } = await params;
    const t = await getTranslations({ locale, namespace: "about" });
    return {
        title: locale === "pt" ? "Sobre" : "About",
        description: t("p1"),
        alternates: {
            canonical: `https://animecaos.vercel.app/${locale}/about`,
        },
    };
}

export default async function AboutPage({ params }: { params: Promise<{ locale: string }> }) {
    const { locale } = await params;
    return (
        <PageWrapper locale={locale}>
            <AboutContent />
        </PageWrapper>
    );
}
