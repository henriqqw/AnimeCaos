"use client";

import { motion, Variants } from "framer-motion";
import { Tv, Zap, Database, SkipForward, Download, Package } from "lucide-react";
import { useTranslations } from "next-intl";

const ICONS = [Tv, Zap, Database, SkipForward, Download, Package];

const containerVariants: Variants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.1 } },
};

const cardVariants: Variants = {
    hidden: { opacity: 0, y: 32 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.4, 0, 0.2, 1] } },
};

export default function Features() {
    const t = useTranslations("features");
    const items = t.raw("items") as Array<{ title: string; desc: string }>;

    return (
        <section className="section" id="features">
            <div className="container">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: 24 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-80px" }}
                    transition={{ duration: 0.6 }}
                    style={{ textAlign: "center", marginBottom: "4rem" }}
                >
                    <h2 className="heading-lg" style={{ marginBottom: "1rem" }}>
                        {t("title")}
                    </h2>
                    <p style={{ color: "var(--text-muted)", fontSize: "1.1rem" }}>{t("sub")}</p>
                </motion.div>

                {/* Grid */}
                <motion.div
                    variants={containerVariants}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: "-60px" }}
                    style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
                        gap: "1px",
                        background: "var(--border)",
                        borderRadius: "var(--radius-xl)",
                        overflow: "hidden",
                        border: "1px solid var(--border)",
                    }}
                >
                    {items.map((item, i) => {
                        const Icon = ICONS[i];
                        return (
                            <motion.div
                                key={i}
                                variants={cardVariants}
                                className="feature-card glass"
                                style={{
                                    background: "var(--bg-2)",
                                    borderRadius: 0,
                                }}
                            >
                                <div className="feature-icon">
                                    <Icon size={20} />
                                </div>
                                <h3 style={{ fontSize: "1.05rem", fontWeight: 700, marginBottom: "0.5rem" }}>
                                    {item.title}
                                </h3>
                                <p style={{ fontSize: "0.9rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
                                    {item.desc}
                                </p>
                            </motion.div>
                        );
                    })}
                </motion.div>
            </div>
        </section>
    );
}
