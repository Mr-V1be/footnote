"use client";

import Image from "next/image";
import { useEffect, useRef } from "react";

import { useMediaQuery } from "@/shared/hooks/useMediaQuery";
import { useResolvedTheme } from "@/shared/theme/useResolvedTheme";

/** Where the landing's recordings of the product live (see e2e/landing). */
const MEDIA_ROOT = "/landing";

/**
 * A short silent loop of the product in the current theme. It plays only
 * while on screen, and not at all for those who ask for reduced motion:
 * they see its first frame.
 */
export function LoopVideo({
  name,
  label,
  width,
  height,
}: {
  name: string;
  label: string;
  width: number;
  height: number;
}) {
  const theme = useResolvedTheme();
  const still = useMediaQuery("(prefers-reduced-motion: reduce)");
  const video = useRef<HTMLVideoElement>(null);
  const poster = `${MEDIA_ROOT}/${name}-${theme}.webp`;

  useEffect(() => {
    const element = video.current;
    if (!element || still) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting) void element.play().catch(() => undefined);
      else element.pause();
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [still, theme]);

  if (still) {
    return <Image src={poster} alt={label} width={width} height={height} unoptimized />;
  }
  return (
    <video
      key={theme}
      ref={video}
      src={`${MEDIA_ROOT}/${name}-${theme}.mp4`}
      poster={poster}
      width={width}
      height={height}
      aria-label={label}
      muted
      loop
      playsInline
      preload="metadata"
    />
  );
}
