"use client";

import { motion } from "framer-motion";
import { Download, Github, ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";

const DOWNLOAD_URL = "https://github.com/henriqqw/animecaos/releases/download/v0.1.0/AnimeCaos.v0.1.0.-.Official.Release.zip";
const GITHUB_URL = "https://github.com/henriqqw/animecaos";

export default function DownloadCTA() {
    const t = useTranslations("download");

    return (
        <section className="section" id="download-cta">
            <div className="container">
                <motion.div
                    initial={{ opacity: 0, y: 32 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-80px" }}
                    transition={{ duration: 0.6 }}
                    className="liquid-glass"
                    style={{
                        padding: "clamp(2rem, 5vw, 4rem)",
                        textAlign: "center",
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: "1.5rem",
                    }}
                >
                    <div className="badge">
                        <Download size={11} />
                        {t("version")}
                    </div>

                    <h2 className="heading-lg" style={{ maxWidth: 560 }}>
                        {t("title")}
                    </h2>

                    <p style={{ color: "var(--text-muted)", fontSize: "1.05rem", maxWidth: 460 }}>
                        {t("sub")}
                    </p>

                    <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", justifyContent: "center" }}>
                        <a
                            href={DOWNLOAD_URL}
                            id="cta-download-btn"
                            className="btn btn-primary"
                            style={{ fontSize: "1.05rem", padding: "0.9rem 2rem" }}
                        >
                            <Download size={18} />
                            {t("btn")}
                        </a>
                        <a
                            href={GITHUB_URL}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn btn-ghost"
                            style={{ fontSize: "1.05rem", padding: "0.9rem 2rem" }}
                        >
                            <Github size={18} />
                            GitHub
                            <ArrowRight size={16} />
                        </a>
                    </div>

                    <p style={{ fontSize: "0.78rem", color: "var(--text-subtle)" }}>
                        {t("note")}
                    </p>
                </motion.div>
            </div>
        </section>
    );
}
