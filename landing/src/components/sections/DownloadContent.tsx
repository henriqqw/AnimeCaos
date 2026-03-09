"use client";

import { motion } from "framer-motion";
import { Download, Github, Terminal, Monitor, Chrome, Package } from "lucide-react";
import { useTranslations } from "next-intl";

const DOWNLOAD_URL = "https://github.com/henriqqw/animecaos/releases/download/v0.1.0/AnimeCaos.v0.1.0.-.Official.Release.zip";

const CHANGELOG = [
    "Painel de Controle com integração AniList (capas + sinopses PT-BR)",
    "Watchlist (Favoritos) salva em watchlist.json local",
    "Download nativo via yt-dlp com progresso em tempo real",
    "Auto-Play: avança automaticamente para o próximo episódio",
    "Interface Glassmorphism com PySide6",
];

const REQ_ICONS = [Monitor, Chrome, Terminal, Package];

export default function DownloadContent() {
    const t = useTranslations("download");
    const reqItems = t.raw("req_items") as string[];

    return (
        <div style={{ position: "relative", zIndex: 1, paddingTop: "8rem", paddingBottom: "6rem" }}>
            <div className="container">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    style={{ marginBottom: "3.5rem" }}
                >
                    <div className="badge" style={{ marginBottom: "1.25rem" }}>
                        <Download size={11} />
                        {t("version")}
                    </div>
                    <h1 className="heading-lg">{t("title")}</h1>
                </motion.div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1.5rem" }}>
                    {/* Main download card */}
                    <motion.div
                        initial={{ opacity: 0, y: 32 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6, delay: 0.1 }}
                        className="liquid-glass"
                        style={{ padding: "2.5rem", display: "flex", flexDirection: "column", gap: "1.5rem" }}
                    >
                        <div>
                            <h2 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: "0.5rem" }}>
                                Setup_Animecaos.exe
                            </h2>
                            <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>{t("sub")}</p>
                        </div>

                        <a
                            href={DOWNLOAD_URL}
                            id="download-exe-btn"
                            className="btn btn-primary"
                            style={{ fontSize: "1rem", padding: "0.9rem 1.5rem", justifyContent: "center" }}
                        >
                            <Download size={18} />
                            {t("btn")}
                        </a>

                        <div
                            style={{
                                fontSize: "0.85rem",
                                color: "var(--text)",
                                background: "rgba(230, 63, 63, 0.15)",
                                border: "1px solid rgba(230, 63, 63, 0.3)",
                                padding: "0.85rem 1.25rem",
                                borderRadius: "var(--radius)",
                                fontWeight: 500,
                                textAlign: "center"
                            }}
                        >
                            {t("note")}
                        </div>

                        {/* Changelog */}
                        <div style={{ borderTop: "1px solid var(--border)", paddingTop: "1.25rem" }}>
                            <p style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--text-subtle)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "0.75rem" }}>
                                v0.1.0 changelog
                            </p>
                            <ul style={{ display: "flex", flexDirection: "column", gap: "0.5rem", listStyle: "none" }}>
                                {CHANGELOG.map((item, i) => (
                                    <li key={i} style={{ display: "flex", gap: "0.5rem", fontSize: "0.85rem", color: "var(--text-muted)" }}>
                                        <span style={{ color: "var(--accent)", flexShrink: 0 }}>✓</span>
                                        {item}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </motion.div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                        {/* Requirements */}
                        <motion.div
                            initial={{ opacity: 0, y: 32 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.6, delay: 0.2 }}
                            className="glass"
                            style={{ padding: "1.75rem", borderRadius: "var(--radius-lg)" }}
                        >
                            <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: "1rem" }}>{t("requirements")}</h3>
                            <div style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
                                {reqItems.map((req, i) => {
                                    const Icon = REQ_ICONS[i] ?? Package;
                                    return (
                                        <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                                            <div className="feature-icon" style={{ width: 32, height: 32, margin: 0, flexShrink: 0 }}>
                                                <Icon size={14} />
                                            </div>
                                            <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>{req}</p>
                                        </div>
                                    );
                                })}
                            </div>
                        </motion.div>

                        {/* Source install */}
                        <motion.div
                            initial={{ opacity: 0, y: 32 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.6, delay: 0.3 }}
                            className="glass"
                            style={{ padding: "1.75rem", borderRadius: "var(--radius-lg)" }}
                        >
                            <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: "1rem" }}>{t("source_title")}</h3>
                            <div className="code-block">
                                <div><span className="comment"># Clone e instale</span></div>
                                <div><span className="cmd">git</span> clone https://github.com/henriqqw/animecaos.git</div>
                                <div><span className="cmd">cd</span> animecaos</div>
                                <div><span className="cmd">python</span> -m venv venv</div>
                                <div><span className="cmd">venv\Scripts\activate</span></div>
                                <div><span className="cmd">pip</span> install -r requirements.txt</div>
                                <div><span className="cmd">python</span> main.py</div>
                            </div>
                            <a
                                href="https://github.com/henriqqw/animecaos"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="btn btn-ghost"
                                style={{ marginTop: "1rem", fontSize: "0.875rem" }}
                            >
                                <Github size={15} />
                                Ver no GitHub
                            </a>
                        </motion.div>
                    </div>
                </div>
            </div>
        </div>
    );
}
