"use client";

import Image from "next/image";

import { useMediaPath } from "./useMediaPath";

/** A screenshot of the product in the language and the theme the page is shown in. */
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
  const media = useMediaPath();
  return <Image src={media(name, "webp")} alt={alt} width={width} height={height} unoptimized />;
}
