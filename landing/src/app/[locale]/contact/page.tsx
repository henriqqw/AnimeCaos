import type { Metadata } from "next";
import PageWrapper from "@/components/layout/PageWrapper";
import ContactContent from "@/components/sections/ContactContent";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
    const { locale } = await params;
    const isPt = locale === "pt";
    return {
        title: isPt ? "Contato" : "Contact",
        description: isPt
            ? "Entre em contato com caosdev — criador do AnimeCaos. GitHub, Discord, Twitter, Email."
            : "Get in touch with caosdev — AnimeCaos creator. GitHub, Discord, Twitter, Email.",
        alternates: { canonical: `https://animecaos.vercel.app/${locale}/contact` },
    };
}

export default async function ContactPage({ params }: { params: Promise<{ locale: string }> }) {
    const { locale } = await params;
    return (
        <PageWrapper locale={locale}>
            <ContactContent />
        </PageWrapper>
    );
}
