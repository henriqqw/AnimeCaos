import { useEffect, useRef, useState } from "react";
import { api } from "./api";
export default function Image({
  src,
  alt = "",
  onError,
  onLoadFailure,
  ...props
}: React.ImgHTMLAttributes<HTMLImageElement> & { onLoadFailure?: () => void }) {
  const [value, setValue] = useState(""),
    [visible, setVisible] = useState(false);
  const ref = useRef<HTMLImageElement>(null);
  const failureHandler = useRef(onLoadFailure);
  useEffect(() => { failureHandler.current = onLoadFailure; }, [onLoadFailure]);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" },
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    let active = true;
    if (visible && typeof src === "string")
      api
        .Image(src)
        .then((v) => {
          if (active) setValue(v);
        })
        .catch(() => {
          if (active) {
            setValue("");
            failureHandler.current?.();
          }
        });
    return () => {
      active = false;
    };
  }, [src, visible]);
  return <img {...props} ref={ref} src={value || undefined} alt={alt} onError={(event) => { onError?.(event); onLoadFailure?.(); }} />;
}
