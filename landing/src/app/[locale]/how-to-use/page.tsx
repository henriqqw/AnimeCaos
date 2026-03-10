import type { Metadata } from "next";
import PageWrapper from "@/components/layout/PageWrapper";
import HowToContent from "@/components/sections/HowToContent";
import { buildLocalizedMetadata, toAppLocale } from "@/lib/seo";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
    const locale = toAppLocale((await params).locale);
    const isPt = locale === "pt";

    return buildLocalizedMetadata({
        locale,
        pathname: "/how-to-use",
        title: isPt ? "Como Usar o AnimeCaos" : "How to Use AnimeCaos",
        description: isPt
            ? "Aprenda a usar o AnimeCaos em quatro passos: instalar, pesquisar, selecionar e assistir."
            : "Learn how to use AnimeCaos in four steps: install, search, select, and watch.",
    });
}

export default async function HowToPage({ params }: { params: Promise<{ locale: string }> }) {
    const { locale } = await params;
    return (
        <PageWrapper locale={locale}>
            <HowToContent />
        </PageWrapper>
    );
}
