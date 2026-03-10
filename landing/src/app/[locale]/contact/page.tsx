import type { Metadata } from "next";
import PageWrapper from "@/components/layout/PageWrapper";
import ContactContent from "@/components/sections/ContactContent";
import { buildLocalizedMetadata, toAppLocale } from "@/lib/seo";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
    const locale = toAppLocale((await params).locale);
    const isPt = locale === "pt";

    return buildLocalizedMetadata({
        locale,
        pathname: "/contact",
        title: isPt ? "Contato do AnimeCaos" : "Contact AnimeCaos",
        description: isPt
            ? "Entre em contato com o criador do AnimeCaos por GitHub, Discord, Twitter ou email."
            : "Get in touch with the AnimeCaos creator via GitHub, Discord, Twitter, or email.",
    });
}

export default async function ContactPage({ params }: { params: Promise<{ locale: string }> }) {
    const { locale } = await params;
    return (
        <PageWrapper locale={locale}>
            <ContactContent />
        </PageWrapper>
    );
}
