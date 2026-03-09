"use client";

import { motion } from "framer-motion";
import { Download } from "lucide-react";
import { useTranslations } from "next-intl";

const DOWNLOAD_URL = "https://github.com/henriqqw/animecaos/releases/download/v0.1.0/AnimeCaos.v0.1.0.-.Official.Release.zip";

export default function HowToContent() {
    const t = useTranslations("howto");
    const steps = t.raw("steps") as Array<{ num: string; title: string; desc: string }>;

    return (
        <div style={{ position: "relative", zIndex: 1, paddingTop: "8rem", paddingBottom: "6rem" }}>
            <div className="container">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                    style={{ marginBottom: "4rem", maxWidth: 640 }}
                >
                    <h1 className="heading-lg" style={{ marginBottom: "1rem" }}>{t("title")}</h1>
                    <p style={{ color: "var(--text-muted)", fontSize: "1.1rem", lineHeight: 1.6 }}>{t("sub")}</p>
                </motion.div>

                {/* Steps */}
                <div style={{ display: "flex", flexDirection: "column", gap: "2px", position: "relative" }}>
                    {/* Vertical line */}
                    <div
                        aria-hidden
                        style={{
                            position: "absolute",
                            left: "calc(2.5rem)",
                            top: "3rem",
                            bottom: "3rem",
                            width: 1,
                            background: "linear-gradient(180deg, var(--accent) 0%, var(--border) 100%)",
                            opacity: 0.3,
                        }}
                    />

                    {steps.map((step, i) => (
                        <motion.div
                            key={i}
                            initial={{ opacity: 0, x: -24 }}
                            whileInView={{ opacity: 1, x: 0 }}
                            viewport={{ once: true, margin: "-60px" }}
                            transition={{ duration: 0.5, delay: i * 0.1 }}
                            className="glass"
                            style={{
                                display: "flex",
                                alignItems: "flex-start",
                                gap: "1.75rem",
                                padding: "2rem 2.5rem",
                                marginBottom: "1px",
                                borderRadius: i === 0 ? "var(--radius-lg) var(--radius-lg) 0 0" :
                                    i === steps.length - 1 ? "0 0 var(--radius-lg) var(--radius-lg)" : "0",
                                transition: "background 0.2s",
                            }}
                            onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.06)")}
                            onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = "var(--glass-bg)")}
                        >
                            {/* Number */}
                            <div
                                style={{
                                    flexShrink: 0,
                                    width: 48,
                                    height: 48,
                                    borderRadius: "50%",
                                    border: "2px solid",
                                    borderColor: i === 0 ? "var(--accent)" : "var(--border)",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    fontSize: "0.8rem",
                                    fontWeight: 800,
                                    color: i === 0 ? "var(--accent)" : "var(--text-muted)",
                                    background: i === 0 ? "var(--accent-dim)" : "transparent",
                                    zIndex: 1,
                                    position: "relative",
                                }}
                            >
                                {step.num}
                            </div>

                            <div>
                                <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "0.5rem" }}>
                                    {step.title}
                                </h3>
                                <p style={{ color: "var(--text-muted)", lineHeight: 1.6, fontSize: "0.95rem" }}>
                                    {step.desc}
                                </p>
                            </div>
                        </motion.div>
                    ))}
                </div>

                {/* CTA */}
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    style={{ marginTop: "3rem", textAlign: "center" }}
                >
                    <a
                        href={DOWNLOAD_URL}
                        id="howto-download-btn"
                        className="btn btn-primary"
                        style={{ fontSize: "1rem", padding: "0.9rem 2rem" }}
                    >
                        <Download size={18} />
                        Baixar AnimeCaos
                    </a>
                </motion.div>
            </div>
        </div>
    );
}
