"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Download, Github } from "lucide-react";
import { useTranslations } from "next-intl";

const GITHUB = "https://github.com/henriqqw/animecaos";
const DOWNLOAD = "https://github.com/henriqqw/animecaos/releases/tag/v0.1.0";

interface NavbarProps {
    locale: string;
}

export default function Navbar({ locale }: NavbarProps) {
    const t = useTranslations("nav");
    const pathname = usePathname();
    const [scrolled, setScrolled] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);

    useEffect(() => {
        const onScroll = () => setScrolled(window.scrollY > 20);
        window.addEventListener("scroll", onScroll, { passive: true });
        return () => window.removeEventListener("scroll", onScroll);
    }, []);

    useEffect(() => {
        if (mobileOpen) document.body.style.overflow = "hidden";
        else document.body.style.overflow = "";
        return () => { document.body.style.overflow = ""; };
    }, [mobileOpen]);

    const otherLocale = locale === "pt" ? "en" : "pt";
    const otherPath = pathname.replace(`/${locale}`, `/${otherLocale}`);

    const navLinks = [
        { href: `/${locale}`, label: t("home") },
        { href: `/${locale}/about`, label: t("about") },
        { href: `/${locale}/download`, label: t("download") },
        { href: `/${locale}/how-to-use`, label: t("howToUse") },
        { href: `/${locale}/contact`, label: t("contact") },
    ];

    const isActive = (href: string) => {
        if (href === `/${locale}`) return pathname === `/${locale}`;
        return pathname.startsWith(href);
    };

    return (
        <>
            {/* Navbar */}
            <motion.header
                style={{
                    position: "fixed",
                    top: 0,
                    left: 0,
                    right: 0,
                    zIndex: 100,
                    padding: "0.75rem 0",
                    transition: "all 0.3s cubic-bezier(0.4,0,0.2,1)",
                }}
                animate={{
                    backgroundColor: scrolled ? "rgba(8,11,15,0.85)" : "transparent",
                    borderBottomColor: scrolled ? "rgba(255,255,255,0.08)" : "transparent",
                    backdropFilter: scrolled ? "blur(24px) saturate(180%)" : "none",
                }}
                initial={false}
            >
                <div
                    className="container"
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "1rem",
                        borderBottom: scrolled ? "1px solid rgba(255,255,255,0.08)" : "none",
                        paddingBottom: scrolled ? "0.5rem" : 0,
                    }}
                >
                    {/* Logo */}
                    <Link
                        href={`/${locale}`}
                        style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "0.6rem",
                            textDecoration: "none",
                            flex: "0 0 auto",
                        }}
                    >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src="/icon.png" alt="AnimeCaos" width={32} height={32} style={{ borderRadius: 6 }} />
                        <span
                            style={{
                                fontWeight: 800,
                                fontSize: "1.05rem",
                                color: "var(--text)",
                                letterSpacing: "-0.03em",
                            }}
                        >
                            AnimeCaos
                        </span>
                    </Link>

                    {/* Desktop nav */}
                    <nav
                        className="hide-mobile"
                        style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "0.25rem",
                            flex: 1,
                            justifyContent: "center",
                        }}
                    >
                        {/* Bubble pill */}
                        <div
                            className="glass"
                            style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "0.1rem",
                                padding: "0.3rem",
                                borderRadius: "100px",
                            }}
                        >
                            {navLinks.map((link) => (
                                <Link
                                    key={link.href}
                                    href={link.href}
                                    style={{
                                        padding: "0.4rem 1rem",
                                        borderRadius: "100px",
                                        fontSize: "0.875rem",
                                        fontWeight: isActive(link.href) ? 600 : 500,
                                        color: isActive(link.href) ? "var(--text)" : "var(--text-muted)",
                                        textDecoration: "none",
                                        background: isActive(link.href) ? "rgba(255,255,255,0.1)" : "transparent",
                                        transition: "all 0.2s ease",
                                        whiteSpace: "nowrap",
                                    }}
                                >
                                    {link.label}
                                </Link>
                            ))}
                        </div>
                    </nav>

                    {/* Right actions */}
                    <div
                        className="hide-mobile"
                        style={{ display: "flex", alignItems: "center", gap: "0.5rem", flex: "0 0 auto" }}
                    >
                        {/* Locale toggle */}
                        <Link
                            href={otherPath}
                            style={{
                                padding: "0.35rem 0.75rem",
                                borderRadius: "100px",
                                fontSize: "0.8rem",
                                fontWeight: 600,
                                color: "var(--text-muted)",
                                textDecoration: "none",
                                border: "1px solid var(--border)",
                                background: "var(--surface)",
                                backdropFilter: "blur(10px)",
                                transition: "all 0.2s ease",
                                textTransform: "uppercase",
                                letterSpacing: "0.05em",
                            }}
                        >
                            {otherLocale}
                        </Link>

                        <a
                            href={GITHUB}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn btn-ghost"
                            style={{ padding: "0.4rem 0.9rem", fontSize: "0.85rem" }}
                        >
                            <Github size={15} />
                            GitHub
                        </a>

                        <a
                            href={DOWNLOAD}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn btn-primary"
                            style={{ padding: "0.4rem 0.9rem", fontSize: "0.85rem" }}
                        >
                            <Download size={15} />
                            Download
                        </a>
                    </div>

                    {/* Mobile hamburger */}
                    <button
                        className="hide-desktop"
                        onClick={() => setMobileOpen(true)}
                        aria-label="Open menu"
                        style={{
                            marginLeft: "auto",
                            background: "none",
                            border: "1px solid var(--border)",
                            borderRadius: 8,
                            padding: "0.4rem",
                            cursor: "pointer",
                            color: "var(--text)",
                            display: "flex",
                        }}
                    >
                        <Menu size={20} />
                    </button>
                </div>
            </motion.header>

            {/* Mobile Drawer */}
            <AnimatePresence>
                {mobileOpen && (
                    <>
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setMobileOpen(false)}
                            style={{
                                position: "fixed",
                                inset: 0,
                                background: "rgba(0,0,0,0.6)",
                                zIndex: 200,
                                backdropFilter: "blur(4px)",
                            }}
                        />
                        <motion.div
                            initial={{ x: "100%" }}
                            animate={{ x: 0 }}
                            exit={{ x: "100%" }}
                            transition={{ type: "spring", damping: 28, stiffness: 300 }}
                            className="glass-strong"
                            style={{
                                position: "fixed",
                                top: 0,
                                right: 0,
                                bottom: 0,
                                width: "min(320px, 85vw)",
                                zIndex: 300,
                                padding: "1.5rem",
                                display: "flex",
                                flexDirection: "column",
                                gap: "0.5rem",
                            }}
                        >
                            <div
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "space-between",
                                    marginBottom: "1.5rem",
                                }}
                            >
                                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                                    {/* eslint-disable-next-line @next/next/no-img-element */}
                                    <img src="/icon.png" alt="AnimeCaos" width={28} height={28} style={{ borderRadius: 6 }} />
                                    <span style={{ fontWeight: 800, fontSize: "1rem", letterSpacing: "-0.02em" }}>
                                        AnimeCaos
                                    </span>
                                </div>
                                <button
                                    onClick={() => setMobileOpen(false)}
                                    aria-label="Close menu"
                                    style={{
                                        background: "var(--surface)",
                                        border: "1px solid var(--border)",
                                        borderRadius: 8,
                                        padding: "0.4rem",
                                        cursor: "pointer",
                                        color: "var(--text)",
                                        display: "flex",
                                    }}
                                >
                                    <X size={18} />
                                </button>
                            </div>

                            {navLinks.map((link, i) => (
                                <motion.div
                                    key={link.href}
                                    initial={{ opacity: 0, x: 20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: i * 0.05 }}
                                >
                                    <Link
                                        href={link.href}
                                        onClick={() => setMobileOpen(false)}
                                        style={{
                                            display: "block",
                                            padding: "0.85rem 1rem",
                                            borderRadius: 10,
                                            fontWeight: isActive(link.href) ? 600 : 500,
                                            color: isActive(link.href) ? "var(--text)" : "var(--text-muted)",
                                            background: isActive(link.href) ? "rgba(255,255,255,0.08)" : "transparent",
                                            textDecoration: "none",
                                            fontSize: "1rem",
                                            transition: "all 0.2s ease",
                                        }}
                                    >
                                        {link.label}
                                    </Link>
                                </motion.div>
                            ))}

                            <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                                <Link
                                    href={otherPath}
                                    onClick={() => setMobileOpen(false)}
                                    style={{
                                        display: "block",
                                        textAlign: "center",
                                        padding: "0.7rem",
                                        borderRadius: 10,
                                        border: "1px solid var(--border)",
                                        fontSize: "0.875rem",
                                        fontWeight: 600,
                                        color: "var(--text-muted)",
                                        textDecoration: "none",
                                        textTransform: "uppercase",
                                        letterSpacing: "0.05em",
                                    }}
                                >
                                    {otherLocale === "pt" ? "🇧🇷 PT-BR" : "🇺🇸 EN"}
                                </Link>
                                <a
                                    href={DOWNLOAD}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="btn btn-primary"
                                    style={{ justifyContent: "center" }}
                                >
                                    <Download size={16} />
                                    Download v0.1.0
                                </a>
                            </div>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
        </>
    );
}
