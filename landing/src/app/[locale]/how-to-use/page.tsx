import type { Metadata } from "next";
import PageWrapper from "@/components/layout/PageWrapper";
import HowToContent from "@/components/sections/HowToContent";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
    const { locale } = await params;
    const isPt = locale === "pt";
    return {
        title: isPt ? "Como Usar" : "How to Use",
        description: isPt
            ? "Aprenda a usar o AnimeCaos em 4 passos: instalar, pesquisar, selecionar e assistir."
            : "Learn to use AnimeCaos in 4 steps: install, search, select, and watch.",
        alternates: { canonical: `https://animecaos.vercel.app/${locale}/how-to-use` },
    };
}

export default async function HowToPage({ params }: { params: Promise<{ locale: string }> }) {
    const { locale } = await params;
    return (
        <PageWrapper locale={locale}>
            <HowToContent />
        </PageWrapper>
    );
}
