import { Skeleton } from "@/shared/ui/skeleton/Skeleton";

import styles from "./document-screen.module.css";
import sheet from "./sheet.module.css";

const LINE_WIDTHS = ["92%", "100%", "96%", "70%", "100%", "88%", "94%", "60%"];

export function SheetSkeleton() {
  return (
    <div className={sheet.sheet} aria-hidden>
      <div className={styles.skeletonStack}>
        <Skeleton width="40%" height="1.4em" />
        {LINE_WIDTHS.map((width, index) => (
          <Skeleton key={index} width={width} />
        ))}
      </div>
    </div>
  );
}

export function ViewerSkeleton() {
  return (
    <div className={styles.screen} aria-busy>
      <div className={styles.skeletonStack}>
        <Skeleton width="8rem" />
        <Skeleton width="min(28rem, 80%)" height="1.6em" />
        <Skeleton width="12rem" />
      </div>
      <div className={styles.workspace}>
        <div className={styles.sheetColumn}>
          <SheetSkeleton />
        </div>
      </div>
    </div>
  );
}
