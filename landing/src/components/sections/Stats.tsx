"use client";

import { motion, useInView } from "framer-motion";
import { useRef, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

function CountUp({ end, suffix = "" }: { end: number; suffix?: string }) {
    const [count, setCount] = useState(0);
    const ref = useRef<HTMLSpanElement>(null);
    const inView = useInView(ref, { once: true });

    useEffect(() => {
        if (!inView) return;
        let start = 0;
        const duration = 1200;
        const step = duration / end;
        const timer = setInterval(() => {
            start += 1;
            setCount(start);
            if (start >= end) clearInterval(timer);
        }, step);
        return () => clearInterval(timer);
    }, [inView, end]);

    return <span ref={ref}>{count}{suffix}</span>;
}

export default function Stats() {
    const t = useTranslations("stats");

    const items: Array<{ label: string; value: string; numeric: boolean; num?: number }> = [
        { label: t("sources"), value: t("sources_val"), numeric: false },
        { label: t("zero_ads"), value: t("zero_ads_val"), numeric: false },
        { label: t("size"), value: t("size_val"), numeric: false },
        { label: t("open_source"), value: t("open_source_val"), numeric: false },
    ];

    return (
        <section style={{ position: "relative", zIndex: 1, padding: "4rem 0" }}>
            <div className="container">
                <div className="divider" style={{ marginBottom: "3rem" }} />
                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                        gap: "2rem",
                    }}
                >
                    {items.map((item, i) => (
                        <motion.div
                            key={i}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: i * 0.1, duration: 0.5 }}
                            style={{ textAlign: "center" }}
                        >
                            <div
                                style={{
                                    fontSize: "clamp(2.5rem, 5vw, 3.5rem)",
                                    fontWeight: 900,
                                    letterSpacing: "-0.04em",
                                    color: "var(--text)",
                                    lineHeight: 1,
                                    marginBottom: "0.4rem",
                                }}
                            >
                                {item.numeric ? <CountUp end={item.num!} /> : item.value}
                            </div>
                            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontWeight: 500 }}>
                                {item.label}
                            </p>
                        </motion.div>
                    ))}
                </div>
                <div className="divider" style={{ marginTop: "3rem" }} />
            </div>
        </section>
    );
}
