"use client";

import { motion, Variants } from "framer-motion";
import Link from "next/link";
import { Download, Github, ArrowRight, Star } from "lucide-react";
import { useTranslations } from "next-intl";

const DOWNLOAD_URL = "https://github.com/henriqqw/AnimeCaos/releases/download/v0.1.2/AnimeCaos_v0.1.2.exe";
const GITHUB_URL = "https://github.com/henriqqw/animecaos";

const fadeUp: Variants = {
    hidden: { opacity: 0, y: 24 },
    visible: (delay = 0) => ({
        opacity: 1,
        y: 0,
        transition: { duration: 0.6, delay, ease: [0.4, 0, 0.2, 1] },
    }),
};

interface HeroProps {
    locale: string;
}

export default function Hero({ locale }: HeroProps) {
    const t = useTranslations("hero");

    const words1 = t("headline1").split(" ");
    const words2 = t("headline2").split(" ");
    const words3 = t("headline3").split(" ");
    const allWords = [...words1.map(w => ({ w, idx: 0 })), ...words2.map(w => ({ w, idx: 1 })), ...words3.map(w => ({ w, idx: 2 }))];

    return (
        <section
            style={{
                position: "relative",
                zIndex: 1,
                isolation: "isolate",
                minHeight: "100dvh",
                display: "flex",
                alignItems: "center",
                paddingTop: "5rem",
                paddingBottom: "5rem",
                overflow: "hidden",
                backgroundImage: "url('/hero.webp')",
                backgroundSize: "cover",
                backgroundPosition: "center",
                backgroundRepeat: "no-repeat",
                WebkitMaskImage:
                    "linear-gradient(to bottom, rgba(0,0,0,1) 0%, rgba(0,0,0,1) 76%, rgba(0,0,0,0.92) 84%, rgba(0,0,0,0.65) 92%, rgba(0,0,0,0) 100%)",
                maskImage:
                    "linear-gradient(to bottom, rgba(0,0,0,1) 0%, rgba(0,0,0,1) 76%, rgba(0,0,0,0.92) 84%, rgba(0,0,0,0.65) 92%, rgba(0,0,0,0) 100%)",
            }}
        >
            <div
                aria-hidden="true"
                style={{
                    position: "absolute",
                    inset: 0,
                    zIndex: 0,
                    background:
                        "radial-gradient(ellipse at center, rgba(6,8,12,0.45) 0%, rgba(6,8,12,0.7) 55%, rgba(6,8,12,0.86) 100%), linear-gradient(180deg, rgba(6,8,12,0.6) 0%, rgba(6,8,12,0.75) 100%)",
                    pointerEvents: "none",
                }}
            />

            {/* Radial glow */}
            <div
                aria-hidden="true"
                style={{
                    position: "absolute",
                    zIndex: 1,
                    top: "20%",
                    left: "50%",
                    transform: "translate(-50%, -50%)",
                    width: "100vw",
                    maxWidth: "700px",
                    height: "700px",
                    borderRadius: "50%",
                    background: "radial-gradient(ellipse, rgba(230,63,63,0.08) 0%, transparent 70%)",
                    pointerEvents: "none",
                }}
            />

            <div
                aria-hidden="true"
                style={{
                    position: "absolute",
                    inset: 0,
                    zIndex: 2,
                    boxShadow: "inset 0 -140px 110px -90px rgba(8,11,15,0.85)",
                    filter: "blur(10px)",
                    opacity: 0.75,
                    pointerEvents: "none",
                }}
            />

            <div className="container" style={{ position: "relative", zIndex: 3 }}>
                <div
                    style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        textAlign: "center",
                        gap: "2rem",
                        maxWidth: 860,
                        margin: "0 auto",
                    }}
                >
                    {/* Badge */}
                    <motion.div
                        variants={fadeUp}
                        initial="hidden"
                        animate="visible"
                        custom={0}
                    >
                        <div className="badge">
                            <Star size={11} fill="currentColor" />
                            {t("badge")}
                        </div>
                    </motion.div>

                    {/* Headline */}
                    <motion.h1
                        className="heading-xl"
                        variants={fadeUp}
                        initial="hidden"
                        animate="visible"
                        custom={0.1}
                        style={{
                            display: "flex",
                            flexWrap: "wrap",
                            justifyContent: "center",
                            gap: "0 0.3em",
                            textShadow: "0 10px 30px rgba(0,0,0,0.55)",
                        }}
                    >
                        {allWords.map(({ w, idx }, i) => (
                            <motion.span
                                key={i}
                                style={{
                                    color: idx === 1 ? "#ff4d4d" : "#f8fbff",
                                    display: "inline-block",
                                }}
                                initial={{ opacity: 0, y: 30 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.5, delay: 0.2 + i * 0.06, ease: [0.4, 0, 0.2, 1] }}
                            >
                                {w}
                            </motion.span>
                        ))}
                    </motion.h1>

                    {/* Sub */}
                    <motion.p
                        variants={fadeUp}
                        initial="hidden"
                        animate="visible"
                        custom={0.55}
                        style={{
                            fontSize: "clamp(1rem, 2vw, 1.2rem)",
                            color: "rgba(240, 245, 255, 0.9)",
                            maxWidth: 580,
                            lineHeight: 1.65,
                            textShadow: "0 6px 20px rgba(0,0,0,0.5)",
                        }}
                    >
                        {t("sub")}
                    </motion.p>

                    {/* CTAs */}
                    <motion.div
                        variants={fadeUp}
                        initial="hidden"
                        animate="visible"
                        custom={0.7}
                        style={{
                            display: "flex",
                            gap: "0.75rem",
                            flexWrap: "wrap",
                            justifyContent: "center",
                            filter: "drop-shadow(0 10px 20px rgba(0,0,0,0.45))",
                        }}
                    >
                        <a
                            href={DOWNLOAD_URL}
                            id="hero-download-btn"
                            className="btn btn-primary"
                            style={{
                                fontSize: "1rem",
                                padding: "0.85rem 1.75rem",
                                border: "1px solid rgba(255,255,255,0.18)",
                                boxShadow: "0 12px 30px rgba(230,63,63,0.5)",
                            }}
                        >
                            <Download size={18} />
                            {t("cta_download")}
                        </a>
                        <a
                            href={GITHUB_URL}
                            target="_blank"
                            rel="noopener noreferrer"
                            id="hero-github-btn"
                            className="btn btn-ghost"
                            style={{
                                fontSize: "1rem",
                                padding: "0.85rem 1.75rem",
                                background: "rgba(10, 14, 22, 0.78)",
                                color: "#f8fbff",
                                border: "1px solid rgba(255,255,255,0.22)",
                                backdropFilter: "blur(8px)",
                            }}
                        >
                            <Github size={18} />
                            {t("cta_github")}
                        </a>
                    </motion.div>

                    {/* Version hint */}
                    <motion.div
                        variants={fadeUp}
                        initial="hidden"
                        animate="visible"
                        custom={0.85}
                    >
                        <Link
                            href={`/${locale}/download`}
                            style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "0.4rem",
                                fontSize: "0.82rem",
                                color: "rgba(225, 234, 252, 0.86)",
                                textDecoration: "none",
                                transition: "color 0.2s",
                                textShadow: "0 4px 14px rgba(0,0,0,0.45)",
                            }}
                        >
                            {t("cta_version")}
                            <ArrowRight size={13} />
                        </Link>
                    </motion.div>

                    {/* App preview card */}
                    <motion.div
                        variants={fadeUp}
                        initial="hidden"
                        animate="visible"
                        custom={1}
                        style={{ width: "100%", maxWidth: 800, marginTop: "1rem" }}
                    >
                        <div
                            className="liquid-glass"
                            style={{
                                padding: "1.5rem",
                                borderRadius: "var(--radius-xl)",
                                overflow: "hidden",
                            }}
                        >
                            {/* Fake terminal / app preview */}
                            <div style={{ display: "flex", gap: "0.4rem", marginBottom: "1.2rem" }}>
                                {["#ff5f56", "#ffbd2e", "#27c93f"].map((c) => (
                                    <div key={c} style={{ width: 12, height: 12, borderRadius: "50%", background: c }} />
                                ))}
                            </div>
                            <div
                                className="code-block"
                                style={{ textAlign: "left", background: "rgba(0,0,0,0.6)", borderRadius: 10 }}
                            >
                                <div><span className="comment"># AnimeCaos v0.1.2</span></div>
                                <div><span className="cmd">→</span> Pesquisando: <strong style={{ color: "#e2c08d" }}>attack on titan</strong></div>
                                <div style={{ marginTop: "0.3rem", color: "#58a6ff" }}>✓ 3 fontes verificadas em 1.2s</div>
                                <div style={{ color: "#3fb950" }}>✓ Capa AniList carregada</div>
                                <div style={{ color: "#3fb950" }}>✓ 87 episódios encontrados</div>
                                <div style={{ marginTop: "0.5rem" }}><span className="cmd">→</span> Reproduzindo EP 01 via mpv...</div>
                            </div>
                        </div>
                    </motion.div>
                </div>
            </div>
        </section>
    );
}
