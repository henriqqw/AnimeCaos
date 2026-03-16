"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import { useTranslations } from "next-intl";

const fadeUp: import("framer-motion").Variants = {
    hidden: { opacity: 0, y: 32 },
    visible: (delay: number = 0) => ({
        opacity: 1,
        y: 0,
        transition: { duration: 0.7, delay, ease: "easeOut" as const },
    }),
};

function MacOSWindow({
    title,
    children,
    delay = 0,
    style = {},
}: {
    title: string;
    children: React.ReactNode;
    delay?: number;
    style?: React.CSSProperties;
}) {
    return (
        <motion.div
            variants={fadeUp}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-80px" }}
            custom={delay}
            style={{
                width: "100%",
                borderRadius: 16,
                overflow: "hidden",
                background: "rgba(20, 24, 30, 0.85)",
                border: "1px solid rgba(255,255,255,0.10)",
                boxShadow:
                    "0 32px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.05), inset 0 1px 0 rgba(255,255,255,0.08)",
                backdropFilter: "blur(24px) saturate(160%)",
                ...style,
            }}
        >
            {/* Title Bar */}
            <div
                style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    padding: "0.75rem 1rem",
                    background: "rgba(255,255,255,0.04)",
                    borderBottom: "1px solid rgba(255,255,255,0.07)",
                    position: "relative",
                }}
            >
                {/* Traffic lights */}
                <div style={{ display: "flex", gap: "0.4rem" }}>
                    {["#ff5f56", "#ffbd2e", "#27c93f"].map((c) => (
                        <div
                            key={c}
                            style={{
                                width: 12,
                                height: 12,
                                borderRadius: "50%",
                                background: c,
                                boxShadow: `0 0 6px ${c}55`,
                            }}
                        />
                    ))}
                </div>
                {/* Centered title */}
                <span
                    style={{
                        position: "absolute",
                        left: "50%",
                        transform: "translateX(-50%)",
                        fontSize: "0.75rem",
                        fontWeight: 500,
                        color: "rgba(240,242,245,0.35)",
                        letterSpacing: "0.02em",
                        pointerEvents: "none",
                        whiteSpace: "nowrap",
                    }}
                >
                    {title}
                </span>
            </div>

            {/* Content */}
            {children}
        </motion.div>
    );
}

export default function Screenshots() {
    const t = useTranslations("screenshots");

    return (
        <section
            className="section"
            style={{ position: "relative", zIndex: 1, paddingTop: "3rem" }}
        >
            {/* Ambient glow */}
            <div
                aria-hidden="true"
                style={{
                    position: "absolute",
                    bottom: "20%",
                    left: "50%",
                    transform: "translateX(-50%)",
                    width: "80vw",
                    maxWidth: 900,
                    height: 400,
                    background:
                        "radial-gradient(ellipse, rgba(230,63,63,0.06) 0%, transparent 70%)",
                    pointerEvents: "none",
                }}
            />

            <div className="container">
                {/* Section header */}
                <motion.div
                    variants={fadeUp}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true }}
                    custom={0}
                    style={{ textAlign: "center", marginBottom: "3.5rem" }}
                >
                    <p
                        style={{
                            fontSize: "0.8rem",
                            fontWeight: 600,
                            letterSpacing: "0.12em",
                            textTransform: "uppercase",
                            color: "var(--accent)",
                            marginBottom: "0.75rem",
                        }}
                    >
                        {t("label")}
                    </p>
                    <h2 className="heading-md" style={{ color: "var(--text)" }}>
                        {t("title")}
                    </h2>
                </motion.div>

                {/* Primary screenshot – App */}
                <MacOSWindow title="AnimeCaos — Biblioteca" delay={0.1}>
                    <div
                        style={{
                            position: "relative",
                            width: "100%",
                            overflow: "hidden",
                        }}
                    >
                        <Image
                            src="/screenshot2.png"
                            alt="AnimeCaos – tela principal do app"
                            width={1397}
                            height={926}
                            style={{ width: "100%", height: "auto", display: "block" }}
                            sizes="(max-width: 768px) 100vw, 1000px"
                            priority
                        />
                    </div>
                </MacOSWindow>

                {/* Caption */}
                <motion.p
                    variants={fadeUp}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true }}
                    custom={0.25}
                    style={{
                        textAlign: "center",
                        fontSize: "0.85rem",
                        color: "var(--text-subtle)",
                        marginTop: "1rem",
                        marginBottom: "3rem",
                        letterSpacing: "0.01em",
                    }}
                >
                    {t("caption_app")}
                </motion.p>

                {/* Secondary screenshot – Player (slightly smaller, indented) */}
                <div style={{ padding: "0 3%" }}>
                    <MacOSWindow title="AnimeCaos — Player" delay={0.3}>
                        <div
                            style={{
                                position: "relative",
                                width: "100%",
                                overflow: "hidden",
                            }}
                        >
                            <Image
                                src="/screenshot.png"
                                alt="AnimeCaos – player integrado"
                                width={1444}
                                height={873}
                                style={{ width: "100%", height: "auto", display: "block" }}
                                sizes="(max-width: 768px) 100vw, 860px"
                            />
                        </div>
                    </MacOSWindow>
                </div>

                {/* Caption */}
                <motion.p
                    variants={fadeUp}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true }}
                    custom={0.45}
                    style={{
                        textAlign: "center",
                        fontSize: "0.85rem",
                        color: "var(--text-subtle)",
                        marginTop: "1rem",
                        letterSpacing: "0.01em",
                    }}
                >
                    {t("caption_player")}
                </motion.p>
            </div>
        </section>
    );
}
