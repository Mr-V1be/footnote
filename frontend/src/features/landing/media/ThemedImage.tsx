"use client";

import Image from "next/image";

import { useResolvedTheme } from "@/shared/theme/useResolvedTheme";

/** A screenshot of the product in the theme the page is shown in. */
export function ThemedImage({
  name,
  alt,
  width,
  height,
}: {
  name: string;
  alt: string;
  width: number;
  height: number;
}) {
  const theme = useResolvedTheme();
  return (
    <Image
      src={`/landing/${name}-${theme}.webp`}
      alt={alt}
      width={width}
      height={height}
      unoptimized
    />
  );
}
