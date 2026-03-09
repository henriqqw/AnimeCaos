import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";

interface PageWrapperProps {
    children: React.ReactNode;
    locale: string;
}

export default function PageWrapper({ children, locale }: PageWrapperProps) {
    return (
        <div style={{ display: "flex", flexDirection: "column", minHeight: "100dvh" }}>
            <Navbar locale={locale} />
            <main style={{ flex: 1 }}>{children}</main>
            <Footer locale={locale} />
        </div>
    );
}
