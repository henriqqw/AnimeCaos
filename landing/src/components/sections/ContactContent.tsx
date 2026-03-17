"use client";

import { motion } from "framer-motion";
import { Github, Twitter, Mail, MessageCircle, Instagram, Linkedin, ExternalLink } from "lucide-react";
import { useTranslations } from "next-intl";

const SOCIALS = [
    {
        icon: Github,
        label: "GitHub",
        handle: "@henriqqw",
        href: "https://github.com/henriqqw",
        desc: "Código & Projetos",
    },
    {
        icon: Twitter,
        label: "Twitter / X",
        handle: "@getanimecaos",
        href: "https://x.com/getanimecaos",
        desc: "Updates & posts",
    },
    {
        icon: MessageCircle,
        label: "Discord",
        handle: "chaosphory",
        href: "https://discord.com/users/chaosphory",
        desc: "Chat direto",
    },
    {
        icon: Instagram,
        label: "Instagram",
        handle: "@getanimecaos",
        href: "https://www.instagram.com/getanimecaos/",
        desc: "Conteúdo & updates",
    },
    {
        icon: Linkedin,
        label: "LinkedIn",
        handle: "henrique-lanzoni",
        href: "https://www.linkedin.com/in/henrique-lanzoni-ab0828371/",
        desc: "Profissional",
    },
    {
        icon: Mail,
        label: "Email",
        handle: "lanzonicmpny13@gmail.com",
        href: "mailto:lanzonicmpny13@gmail.com",
        desc: "Direto na caixa",
    },
];

export default function ContactContent() {
    const t = useTranslations("contact");

    return (
        <div style={{ position: "relative", zIndex: 1, paddingTop: "8rem", paddingBottom: "6rem" }}>
            <div className="container">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    style={{ marginBottom: "4rem", maxWidth: 540 }}
                >
                    <h1 className="heading-lg" style={{ marginBottom: "1rem" }}>{t("title")}</h1>
                    <p style={{ color: "var(--text-muted)", fontSize: "1.05rem", lineHeight: 1.6 }}>{t("sub")}</p>
                </motion.div>

                {/* GitHub CTA */}
                <motion.a
                    href="https://github.com/henriqqw/animecaos/issues"
                    target="_blank"
                    rel="noopener noreferrer"
                    id="github-issue-btn"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.15 }}
                    className="liquid-glass"
                    style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "1.5rem 2rem",
                        borderRadius: "var(--radius-lg)",
                        textDecoration: "none",
                        color: "var(--text)",
                        marginBottom: "2.5rem",
                        cursor: "pointer",
                        flexWrap: "wrap",
                        gap: "1rem",
                    }}
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.99 }}
                >
                    <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                        <div className="feature-icon" style={{ width: 44, height: 44, margin: 0 }}>
                            <Github size={20} />
                        </div>
                        <div>
                            <p style={{ fontWeight: 700, fontSize: "1rem", marginBottom: "0.2rem" }}>{t("issue")}</p>
                            <p style={{ fontSize: "0.83rem", color: "var(--text-muted)" }}>
                                github.com/henriqqw/animecaos/issues
                            </p>
                        </div>
                    </div>
                    <ExternalLink size={18} style={{ color: "var(--text-muted)" }} />
                </motion.a>

                {/* Social grid */}
                <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.3 }}
                    style={{
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        color: "var(--text-subtle)",
                        textTransform: "uppercase",
                        letterSpacing: "0.1em",
                        marginBottom: "1rem",
                    }}
                >
                    {t("links_title")}
                </motion.p>

                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                        gap: "1px",
                        border: "1px solid var(--border)",
                        borderRadius: "var(--radius-lg)",
                        overflow: "hidden",
                    }}
                >
                    {SOCIALS.map(({ icon: Icon, label, handle, href, desc }, i) => (
                        <motion.a
                            key={i}
                            href={href}
                            target={href.startsWith("mailto") ? undefined : "_blank"}
                            rel="noopener noreferrer"
                            initial={{ opacity: 0, y: 16 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: i * 0.07 }}
                            whileHover={{ backgroundColor: "rgba(255,255,255,0.06)" }}
                            style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "1rem",
                                padding: "1.25rem 1.5rem",
                                background: "var(--bg-2)",
                                textDecoration: "none",
                                color: "var(--text)",
                                transition: "background 0.2s",
                            }}
                        >
                            <div className="feature-icon" style={{ width: 40, height: 40, margin: 0, flexShrink: 0 }}>
                                <Icon size={18} />
                            </div>
                            <div style={{ flex: 1, minWidth: 0 }}>
                                <p style={{ fontWeight: 600, fontSize: "0.9rem" }}>{label}</p>
                                <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                    {handle}
                                </p>
                            </div>
                            <p style={{ fontSize: "0.75rem", color: "var(--text-subtle)", whiteSpace: "nowrap", flexShrink: 0 }}>
                                {desc}
                            </p>
                        </motion.a>
                    ))}
                </div>
            </div>
        </div>
    );
}
