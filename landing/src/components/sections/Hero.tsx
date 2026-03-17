"use client";

import { useEffect, useMemo, useRef, useState } from "react";
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

type TerminalLine = {
    text: string;
    color?: string;
    marginTop?: string;
};

export default function Hero({ locale }: HeroProps) {
    const t = useTranslations("hero");
    const canvasContainerRef = useRef<HTMLDivElement | null>(null);
    const terminalLines: TerminalLine[] = useMemo(
        () => [
            { text: "# AnimeCaos v0.1.2" },
            { text: "-> Pesquisando: attack on titan" },
            { text: "✓ 3 fontes verificadas em 1.2s", color: "#58a6ff", marginTop: "0.3rem" },
            { text: "✓ Capa AniList carregada", color: "#3fb950" },
            { text: "✓ 87 episodios encontrados", color: "#3fb950" },
            { text: "-> Reproduzindo EP 01 via mpv...", marginTop: "0.5rem" },
        ],
        []
    );
    const [typedLines, setTypedLines] = useState<string[]>(() => terminalLines.map(() => ""));
    const [showCursor, setShowCursor] = useState(true);
    const [terminalWindowVisible, setTerminalWindowVisible] = useState(true);
    const [terminalWindowMinimized, setTerminalWindowMinimized] = useState(false);

    useEffect(() => {
        const cursorTimer = setInterval(() => {
            setShowCursor((prev) => !prev);
        }, 520);

        return () => clearInterval(cursorTimer);
    }, []);

    useEffect(() => {
        let timeout: ReturnType<typeof setTimeout> | undefined;
        let cancelled = false;
        let lineIndex = 0;
        let charIndex = 0;

        const resetLines = () => terminalLines.map(() => "");
        setTypedLines(resetLines());

        const typeNext = () => {
            if (cancelled) return;

            const fullLine = terminalLines[lineIndex].text;

            if (charIndex <= fullLine.length) {
                setTypedLines((prev) => {
                    const next = [...prev];
                    next[lineIndex] = fullLine.slice(0, charIndex);
                    return next;
                });
                charIndex += 1;
                timeout = setTimeout(typeNext, lineIndex === 0 ? 32 : 24);
                return;
            }

            lineIndex += 1;
            charIndex = 0;

            if (lineIndex < terminalLines.length) {
                timeout = setTimeout(typeNext, 180);
                return;
            }
        };

        typeNext();

        return () => {
            cancelled = true;
            if (timeout) clearTimeout(timeout);
        };
    }, [terminalLines]);

    const activeTypingLine = useMemo(() => {
        const idx = terminalLines.findIndex((line, i) => typedLines[i].length < line.text.length);
        return idx === -1 ? terminalLines.length - 1 : idx;
    }, [terminalLines, typedLines]);

    useEffect(() => {
        const container = canvasContainerRef.current;
        if (!container) return;

        let frameId = 0;
        let disposed = false;
        let renderer: {
            domElement: HTMLCanvasElement;
            render: () => void;
            dispose: () => void;
            resize: () => void;
        } | null = null;

        const init = async () => {
            const THREE = await import("three");
            if (disposed || !container) return;

            const scene = new THREE.Scene();
            const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
            camera.position.z = 20;

            const webglRenderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
            webglRenderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.8));
            webglRenderer.setSize(container.clientWidth, container.clientHeight);
            container.appendChild(webglRenderer.domElement);

            const particlesCount = 1400;
            const cubeSize = 44;

            const spriteCanvas = document.createElement("canvas");
            spriteCanvas.width = 64;
            spriteCanvas.height = 64;
            const ctx = spriteCanvas.getContext("2d");
            if (ctx) {
                const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
                gradient.addColorStop(0, "rgba(255,255,255,1)");
                gradient.addColorStop(0.4, "rgba(255,255,255,0.9)");
                gradient.addColorStop(1, "rgba(255,255,255,0)");
                ctx.fillStyle = gradient;
                ctx.fillRect(0, 0, 64, 64);
            }
            const sprite = new THREE.CanvasTexture(spriteCanvas);

            const particlesGeometry = new THREE.BufferGeometry();
            const posArray = new Float32Array(particlesCount * 3);
            const basePosArray = new Float32Array(particlesCount * 3);
            const phaseArray = new Float32Array(particlesCount);
            for (let i = 0; i < particlesCount * 3; i += 3) {
                posArray[i] = (Math.random() - 0.5) * cubeSize;
                posArray[i + 1] = (Math.random() - 0.5) * cubeSize;
                posArray[i + 2] = (Math.random() - 0.5) * cubeSize;
                basePosArray[i] = posArray[i];
                basePosArray[i + 1] = posArray[i + 1];
                basePosArray[i + 2] = posArray[i + 2];
                phaseArray[i / 3] = Math.random() * Math.PI * 2;
            }
            particlesGeometry.setAttribute("position", new THREE.BufferAttribute(posArray, 3));

            const particlesMaterial = new THREE.PointsMaterial({
                size: 0.15,
                map: sprite,
                transparent: true,
                opacity: 0.75,
                color: 0xe63f3f,
                sizeAttenuation: true,
                depthWrite: false,
            });

            const particlesGeometry2 = new THREE.BufferGeometry();
            const posArray2 = new Float32Array((particlesCount / 2) * 3);
            const basePosArray2 = new Float32Array((particlesCount / 2) * 3);
            const phaseArray2 = new Float32Array(particlesCount / 2);
            for (let i = 0; i < (particlesCount / 2) * 3; i += 3) {
                posArray2[i] = (Math.random() - 0.5) * (cubeSize + 6);
                posArray2[i + 1] = (Math.random() - 0.5) * (cubeSize + 6);
                posArray2[i + 2] = (Math.random() - 0.5) * (cubeSize + 6);
                basePosArray2[i] = posArray2[i];
                basePosArray2[i + 1] = posArray2[i + 1];
                basePosArray2[i + 2] = posArray2[i + 2];
                phaseArray2[i / 3] = Math.random() * Math.PI * 2;
            }
            particlesGeometry2.setAttribute("position", new THREE.BufferAttribute(posArray2, 3));

            const particlesMaterial2 = new THREE.PointsMaterial({
                size: 0.11,
                map: sprite,
                transparent: true,
                opacity: 0.42,
                color: 0xaab8d6,
                sizeAttenuation: true,
                depthWrite: false,
            });

            const group = new THREE.Group();
            const points1 = new THREE.Points(particlesGeometry, particlesMaterial);
            const points2 = new THREE.Points(particlesGeometry2, particlesMaterial2);
            group.add(points1);
            group.add(points2);
            scene.add(group);

            scene.add(new THREE.AmbientLight(0xffffff, 0.45));
            const pointLight = new THREE.PointLight(0xffffff, 0.6);
            pointLight.position.set(10, 10, 10);
            scene.add(pointLight);

            const position1 = particlesGeometry.getAttribute("position");
            const position2 = particlesGeometry2.getAttribute("position");
            const animate = () => {
                if (disposed) return;

                const t = performance.now() * 0.001;

                for (let i = 0; i < particlesCount; i++) {
                    const idx = i * 3;
                    const p = phaseArray[i];
                    posArray[idx] = basePosArray[idx] + Math.cos(t * 0.35 + p * 0.7) * 0.16;
                    posArray[idx + 1] = basePosArray[idx + 1] + Math.sin(t * 0.55 + p) * 0.34;
                    posArray[idx + 2] = basePosArray[idx + 2] + Math.cos(t * 0.25 + p * 0.4) * 0.1;
                }
                position1.needsUpdate = true;

                for (let i = 0; i < particlesCount / 2; i++) {
                    const idx = i * 3;
                    const p = phaseArray2[i];
                    posArray2[idx] = basePosArray2[idx] + Math.cos(t * 0.42 + p * 0.6) * 0.22;
                    posArray2[idx + 1] = basePosArray2[idx + 1] + Math.sin(t * 0.65 + p) * 0.42;
                    posArray2[idx + 2] = basePosArray2[idx + 2] + Math.cos(t * 0.3 + p * 0.45) * 0.12;
                }
                position2.needsUpdate = true;

                group.rotation.y += 0.0024;
                group.rotation.x += 0.0012;
                group.position.y = Math.sin(t * 0.45) * 0.45;
                particlesMaterial.opacity = 0.64 + Math.sin(t * 1.9) * 0.06;
                particlesMaterial2.opacity = 0.36 + Math.cos(t * 1.55) * 0.05;

                webglRenderer.render(scene, camera);
                frameId = requestAnimationFrame(animate);
            };
            animate();

            const resize = () => {
                if (!container) return;
                camera.aspect = container.clientWidth / container.clientHeight;
                camera.updateProjectionMatrix();
                webglRenderer.setSize(container.clientWidth, container.clientHeight);
            };
            window.addEventListener("resize", resize);

            renderer = {
                domElement: webglRenderer.domElement,
                render: () => webglRenderer.render(scene, camera),
                dispose: () => {
                    window.removeEventListener("resize", resize);
                    cancelAnimationFrame(frameId);
                    particlesGeometry.dispose();
                    particlesGeometry2.dispose();
                    particlesMaterial.dispose();
                    particlesMaterial2.dispose();
                    sprite.dispose();
                    webglRenderer.dispose();
                    if (container.contains(webglRenderer.domElement)) {
                        container.removeChild(webglRenderer.domElement);
                    }
                },
                resize,
            };
        };

        init();

        return () => {
            disposed = true;
            renderer?.dispose();
        };
    }, []);

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
                    pointerEvents: "none",
                    overflow: "hidden",
                    mixBlendMode: "screen",
                    opacity: 0.5,
                }}
            >
                <div ref={canvasContainerRef} style={{ position: "absolute", inset: 0 }} />
            </div>

            <div
                aria-hidden="true"
                style={{
                    position: "absolute",
                    inset: 0,
                    zIndex: 3,
                    boxShadow: "inset 0 -140px 110px -90px rgba(8,11,15,0.85)",
                    filter: "blur(10px)",
                    opacity: 0.75,
                    pointerEvents: "none",
                }}
            />

            <div className="container" style={{ position: "relative", zIndex: 4 }}>
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
                            <motion.span
                                style={{ display: "inline-flex" }}
                                animate={{
                                    scale: [1, 1.16, 1],
                                    opacity: [0.9, 1, 0.9],
                                }}
                                transition={{
                                    duration: 2.8,
                                    repeat: Infinity,
                                    ease: "easeInOut",
                                }}
                            >
                                <Star size={11} fill="currentColor" />
                            </motion.span>
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
                        {terminalWindowVisible ? (
                            <div
                                className="liquid-glass"
                                style={{
                                    padding: "1.5rem",
                                    borderRadius: "var(--radius-xl)",
                                    overflow: "hidden",
                                }}
                            >
                                {/* Fake terminal / app preview */}
                                <div
                                    style={{
                                        display: "flex",
                                        justifyContent: "space-between",
                                        alignItems: "center",
                                        gap: "0.35rem",
                                        marginBottom: "1.2rem",
                                    }}
                                >
                                    <div style={{ display: "flex", gap: "0.4rem" }}>
                                        {["#ff5f56", "#ffbd2e", "#27c93f"].map((c) => (
                                            <span
                                                key={c}
                                                aria-hidden="true"
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

                                    <div style={{ display: "flex", gap: "0.35rem" }}>
                                    <button
                                        type="button"
                                        aria-label="Minimizar janela"
                                        onClick={() => setTerminalWindowMinimized((prev) => !prev)}
                                        style={{
                                            width: 22,
                                            height: 18,
                                            borderRadius: 6,
                                            background: "rgba(255,255,255,0.06)",
                                            border: "1px solid rgba(255,255,255,0.1)",
                                            cursor: "pointer",
                                            display: "inline-flex",
                                            alignItems: "center",
                                            justifyContent: "center",
                                            color: "rgba(240,242,245,0.88)",
                                            fontSize: 12,
                                            fontWeight: 700,
                                            lineHeight: 1,
                                        }}
                                    >
                                        -
                                    </button>
                                    <button
                                        type="button"
                                        aria-label="Fechar janela"
                                        onClick={() => setTerminalWindowVisible(false)}
                                        style={{
                                            width: 22,
                                            height: 18,
                                            borderRadius: 6,
                                            background: "rgba(255,95,86,0.18)",
                                            border: "1px solid rgba(255,95,86,0.42)",
                                            cursor: "pointer",
                                            display: "inline-flex",
                                            alignItems: "center",
                                            justifyContent: "center",
                                            color: "rgba(255,210,210,0.95)",
                                            fontSize: 11,
                                            fontWeight: 700,
                                            lineHeight: 1,
                                        }}
                                    >
                                        x
                                    </button>
                                    </div>
                                </div>
                                {!terminalWindowMinimized ? (
                                    <div
                                        className="code-block"
                                        style={{ textAlign: "left", background: "rgba(0,0,0,0.6)", borderRadius: 10 }}
                                    >
                                        {terminalLines.map((line, i) => (
                                            <div
                                                key={`${line.text}-${i}`}
                                                style={{
                                                    color: line.color,
                                                    marginTop: line.marginTop,
                                                    minHeight: "1.7em",
                                                }}
                                            >
                                                {i === 0 ? <span className="comment">{typedLines[i]}</span> : typedLines[i]}
                                                {i === activeTypingLine && showCursor ? (
                                                    <span className="cmd" style={{ marginLeft: 2 }}>|</span>
                                                ) : null}
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div
                                        style={{
                                            height: 16,
                                            borderRadius: 8,
                                            background: "rgba(255,255,255,0.08)",
                                            border: "1px solid rgba(255,255,255,0.1)",
                                        }}
                                    />
                                )}
                            </div>
                        ) : (
                            <button
                                type="button"
                                className="btn btn-ghost"
                                onClick={() => {
                                    setTerminalWindowVisible(true);
                                    setTerminalWindowMinimized(false);
                                }}
                                style={{ padding: "0.55rem 1rem", fontSize: "0.9rem" }}
                            >
                                Reabrir janela
                            </button>
                        )}
                    </motion.div>
                </div>
            </div>
        </section>
    );
}


