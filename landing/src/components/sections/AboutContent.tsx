"use client";

import { motion } from "framer-motion";
import {
    Code2, Globe, Cpu, Search, Play, Package,
    GitBranch, ExternalLink
} from "lucide-react";
import { useTranslations } from "next-intl";

const TECH = [
    { icon: Cpu, name: "Python 3.10+", desc: "Core language" },
    { icon: Globe, name: "Selenium", desc: "Web automation & Cloudflare bypass" },
    { icon: Code2, name: "BeautifulSoup", desc: "HTML parsing" },
    { icon: Search, name: "FuzzyWuzzy", desc: "Fuzzy search / typo tolerance" },
    { icon: Play, name: "yt-dlp + mpv", desc: "Stream extraction & playback" },
    { icon: Package, name: "PySide6", desc: "Desktop GUI framework" },
    { icon: GitBranch, name: "AniList GraphQL", desc: "Metadata & cover art API" },
    { icon: Package, name: "PyInstaller", desc: "Standalone .exe distribution" },
];

export default function AboutContent() {
    const t = useTranslations("about");

    return (
        <div
            style={{
                position: "relative",
                zIndex: 1,
                paddingTop: "8rem",
                paddingBottom: "6rem",
            }}
        >
            <div className="container">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    style={{ maxWidth: 760, marginBottom: "4rem" }}
                >
                    <div className="badge" style={{ marginBottom: "1.25rem" }}>
                        <GitBranch size={11} />
                        open source
                    </div>
                    <h1 className="heading-lg" style={{ marginBottom: "1.75rem" }}>
                        {t("title")}
                    </h1>
                    <div style={{ display: "flex", flexDirection: "column", gap: "1.1rem" }}>
                        {["p1", "p2", "p3"].map((key) => (
                            <p key={key} style={{ color: "var(--text-muted)", fontSize: "1.05rem", lineHeight: 1.75 }}>
                                {t(key as "p1" | "p2" | "p3")}
                            </p>
                        ))}
                    </div>
                </motion.div>

                {/* Tech stack */}
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    style={{ marginBottom: "4rem" }}
                >
                    <h2
                        style={{
                            fontSize: "0.75rem",
                            fontWeight: 700,
                            color: "var(--text-subtle)",
                            textTransform: "uppercase",
                            letterSpacing: "0.12em",
                            marginBottom: "1.5rem",
                        }}
                    >
                        {t("tech_title")}
                    </h2>
                    <div
                        style={{
                            display: "grid",
                            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
                            gap: "1px",
                            border: "1px solid var(--border)",
                            borderRadius: "var(--radius-lg)",
                            overflow: "hidden",
                        }}
                    >
                        {TECH.map(({ icon: Icon, name, desc }, i) => (
                            <motion.div
                                key={i}
                                initial={{ opacity: 0 }}
                                whileInView={{ opacity: 1 }}
                                viewport={{ once: true }}
                                transition={{ delay: i * 0.06 }}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "0.85rem",
                                    padding: "1rem 1.25rem",
                                    background: "var(--bg-2)",
                                    transition: "background 0.2s",
                                }}
                                onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = "var(--surface-hover)")}
                                onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = "var(--bg-2)")}
                            >
                                <div className="feature-icon" style={{ width: 36, height: 36, margin: 0, flexShrink: 0 }}>
                                    <Icon size={16} />
                                </div>
                                <div>
                                    <p style={{ fontWeight: 600, fontSize: "0.9rem" }}>{name}</p>
                                    <p style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>{desc}</p>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </motion.div>

                {/* Open source */}
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    className="liquid-glass"
                    style={{ padding: "2rem 2.5rem", display: "flex", gap: "2rem", alignItems: "flex-start", flexWrap: "wrap" }}
                >
                    <div style={{ flex: 1, minWidth: 260 }}>
                        <h3 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "0.75rem" }}>
                            {t("open_title")}
                        </h3>
                        <p style={{ color: "var(--text-muted)", lineHeight: 1.7, fontSize: "0.95rem" }}>
                            {t("open_desc")}
                        </p>
                    </div>
                    <a
                        href="https://github.com/henriqqw/animecaos"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-ghost"
                        style={{ flexShrink: 0, alignSelf: "flex-start" }}
                    >
                        Ver Repositório
                        <ExternalLink size={14} />
                    </a>
                </motion.div>
            </div>
        </div>
    );
}
