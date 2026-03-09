"use client";

import Link from "next/link";
import { Github, Twitter, Mail, MessageCircle, Instagram, Linkedin } from "lucide-react";
import { useTranslations } from "next-intl";

const LINKS = [
    { icon: Github, label: "GitHub", href: "https://github.com/henriqqw/animecaos" },
    { icon: Twitter, label: "Twitter", href: "https://x.com/chaosphory" },
    { icon: MessageCircle, label: "Discord", href: "https://discord.com/users/chaosphory" },
    { icon: Instagram, label: "Instagram", href: "https://www.instagram.com/henriqqw" },
    { icon: Linkedin, label: "LinkedIn", href: "https://www.linkedin.com/in/henrique-lanzoni-ab0828371/" },
    { icon: Mail, label: "Email", href: "mailto:lanzonicmpny13@gmail.com" },
];

interface FooterProps {
    locale: string;
}

export default function Footer({ locale }: FooterProps) {
    const t = useTranslations("footer");
    const navT = useTranslations("nav");

    const navLinks = [
        { href: `/${locale}`, label: navT("home") },
        { href: `/${locale}/about`, label: navT("about") },
        { href: `/${locale}/download`, label: navT("download") },
        { href: `/${locale}/how-to-use`, label: navT("howToUse") },
        { href: `/${locale}/contact`, label: navT("contact") },
    ];

    return (
        <footer
            style={{
                position: "relative",
                zIndex: 1,
                borderTop: "1px solid var(--border)",
                padding: "3rem 0 2rem",
                marginTop: "auto",
            }}
        >
            <div className="container">
                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                        gap: "2rem",
                        marginBottom: "2.5rem",
                    }}
                >
                    {/* Brand */}
                    <div>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "0.75rem" }}>
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img src="/icon.png" alt="AnimeCaos" width={28} height={28} style={{ borderRadius: 6 }} />
                            <span style={{ fontWeight: 800, fontSize: "1rem" }}>AnimeCaos</span>
                        </div>
                        <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", lineHeight: 1.6, maxWidth: 220 }}>
                            {t("rights")}
                        </p>
                    </div>

                    {/* Nav links */}
                    <div>
                        <p style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-subtle)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "0.75rem" }}>
                            Pages
                        </p>
                        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                            {navLinks.map((l) => (
                                <Link
                                    key={l.href}
                                    href={l.href}
                                    style={{ fontSize: "0.875rem", color: "var(--text-muted)", textDecoration: "none", transition: "color 0.2s" }}
                                >
                                    {l.label}
                                </Link>
                            ))}
                        </div>
                    </div>

                    {/* Social */}
                    <div>
                        <p style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-subtle)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "0.75rem" }}>
                            Links
                        </p>
                        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                            {LINKS.map(({ icon: Icon, label, href }) => (
                                <a
                                    key={label}
                                    href={href}
                                    target={href.startsWith("mailto") ? undefined : "_blank"}
                                    rel="noopener noreferrer"
                                    aria-label={label}
                                    style={{
                                        width: 36,
                                        height: 36,
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        border: "1px solid var(--border)",
                                        borderRadius: 8,
                                        color: "var(--text-muted)",
                                        textDecoration: "none",
                                        background: "var(--surface)",
                                        transition: "all 0.2s ease",
                                    }}
                                    onMouseEnter={(e) => {
                                        (e.currentTarget as HTMLElement).style.color = "var(--text)";
                                        (e.currentTarget as HTMLElement).style.borderColor = "var(--border-hover)";
                                    }}
                                    onMouseLeave={(e) => {
                                        (e.currentTarget as HTMLElement).style.color = "var(--text-muted)";
                                        (e.currentTarget as HTMLElement).style.borderColor = "var(--border)";
                                    }}
                                >
                                    <Icon size={15} />
                                </a>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="divider" />

                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        flexWrap: "wrap",
                        gap: "1rem",
                        marginTop: "1.5rem",
                    }}
                >
                    <p style={{ fontSize: "0.78rem", color: "var(--text-subtle)" }}>
                        {t("made")}{" "}
                        <a href="https://caosdev.vercel.app" target="_blank" rel="noopener noreferrer"
                            style={{ color: "var(--accent)", textDecoration: "none" }}>
                            caosdev
                        </a>
                    </p>
                    <p style={{ fontSize: "0.72rem", color: "var(--text-subtle)", maxWidth: 500, textAlign: "right", lineHeight: 1.4 }}>
                        {t("disclaimer")}
                    </p>
                </div>
            </div>
        </footer>
    );
}
