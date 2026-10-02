import { DocumentListSkeleton } from "@/features/documents/list/DocumentList";
import styles from "@/features/documents/list/documents-screen.module.css";
import { Skeleton } from "@/shared/ui/skeleton/Skeleton";

export default function Loading() {
  return (
    <div className={styles.screen} aria-busy>
      <Skeleton width="10rem" height="1.6em" />
      <Skeleton width="min(24rem, 100%)" height="2.25rem" shape="block" />
      <DocumentListSkeleton />
    </div>
  );
}
