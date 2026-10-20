import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import StartupMascot from "./StartupMascot";
import "./splash-preview.css";

const mascotSource = "/mascots/poses/animecaos-pose-startup-v1.png";
const wordmarkSource = "/animecaos-wordmark.png";
const cycleDurationMs = 8000;
const fadeOutStartsAtMs = 7300;

function SplashPreview() {
  const [elapsed, setElapsed] = useState(0);
  const [motion, setMotion] = useState(1);
  const [speed, setSpeed] = useState(1);
  const [restartCycle, setRestartCycle] = useState(0);
  const [showControls, setShowControls] = useState(false);

  useEffect(() => {
    let frame = 0;
    let lastUpdate = 0;
    const start = performance.now();
    setElapsed(0);
    const tick = (now: number) => {
      if (now - lastUpdate >= 32) {
        setElapsed((now - start) % cycleDurationMs);
        lastUpdate = now;
      }
      frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [restartCycle]);

  const leaving = elapsed >= fadeOutStartsAtMs;
  const entering = elapsed < 32;
  const progress = Math.min(100, (elapsed / fadeOutStartsAtMs) * 100);

  return (
    <main className="preview-splash" aria-label="Prévia contínua da splash AnimeCaos">
      <div className="preview-stage">
        <div className="preview-mascot-wrap">
          <StartupMascot
            src={mascotSource}
            className={`preview-mascot preview-fade${leaving ? " preview-fade-out" : entering ? "" : " preview-fade-in"}`}
            onLoad={() => {}}
            onError={() => {}}
            motionScale={motion}
            speed={speed}
          />
        </div>

        <section className={`preview-brand preview-fade${leaving ? " preview-fade-out" : entering ? "" : " preview-fade-in"}`} aria-label="AnimeCaos">
          <img className="preview-wordmark" src={wordmarkSource} alt="AnimeCaos" />
          <span className="preview-divider" aria-hidden="true" />
          <span className="preview-label">PRÉVIA LOCAL · CICLO INFINITO</span>
          <div
            className="preview-progress"
            role="progressbar"
            aria-label="Progresso simulado da splash"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress)}
            aria-valuetext={`${Math.round(progress)}%`}
          >
            <span className="preview-progress-track" aria-hidden="true">
              <span className="preview-progress-fill" style={{ width: `${progress}%` }} />
            </span>
            <span className="preview-progress-value">{Math.round(progress)}%</span>
          </div>
          <span className="preview-cycle-note">A animação reinicia a cada 8 segundos.</span>
        </section>
      </div>

      <div className="preview-tools">
        <button
          className="preview-tool-button"
          type="button"
          aria-expanded={showControls}
          onClick={() => setShowControls((visible) => !visible)}
        >
          Ajustes da prévia
        </button>
        {showControls && (
          <section className="preview-controls" aria-label="Ajustes de movimento">
            <label>
              <span>Amplitude <output>{motion.toFixed(2)}×</output></span>
              <input type="range" min="0" max="2" step="0.05" value={motion} onChange={(event) => setMotion(Number(event.target.value))} />
            </label>
            <label>
              <span>Velocidade <output>{speed.toFixed(2)}×</output></span>
              <input type="range" min="0.4" max="1.8" step="0.05" value={speed} onChange={(event) => setSpeed(Number(event.target.value))} />
            </label>
            <button className="preview-replay-button" type="button" onClick={() => setRestartCycle((cycle) => cycle + 1)}>
              Reiniciar ciclo
            </button>
          </section>
        )}
      </div>
    </main>
  );
}

createRoot(document.getElementById("splash-preview-root")!).render(
  <StrictMode>
    <SplashPreview />
  </StrictMode>,
);
