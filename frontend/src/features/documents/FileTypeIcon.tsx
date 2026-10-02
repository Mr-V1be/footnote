import { IconFile, IconFileTypeDocx, IconFileTypePdf, type Icon } from "@tabler/icons-react";

const ICONS: Record<string, Icon> = { docx: IconFileTypeDocx, pdf: IconFileTypePdf };

export function FileTypeIcon({ format, className }: { format: string; className?: string }) {
  const Component = ICONS[format] ?? IconFile;
  return <Component className={className} stroke={1.5} aria-hidden />;
}
