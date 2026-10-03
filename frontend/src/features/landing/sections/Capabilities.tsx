import {
  IconHistory,
  IconReceipt,
  IconScan,
  IconShieldLock,
  IconUsersGroup,
  IconWebhook,
  type Icon,
} from "@tabler/icons-react";
import { getTranslations } from "next-intl/server";

import { ThemedImage } from "../media/ThemedImage";
import band from "./band.module.css";
import styles from "./capabilities.module.css";

/** What else a team gets around the check; the large tiles show their screen. */
type TileId = "roles" | "audit" | "scans" | "integrations" | "plans" | "isolation";

const TILES: readonly { id: TileId; icon: Icon; image?: "tile-roles" | "tile-audit" }[] = [
  { id: "roles", icon: IconUsersGroup, image: "tile-roles" },
  { id: "audit", icon: IconHistory, image: "tile-audit" },
  { id: "scans", icon: IconScan },
  { id: "integrations", icon: IconWebhook },
  { id: "plans", icon: IconReceipt },
  { id: "isolation", icon: IconShieldLock },
];

export async function Capabilities() {
  const t = await getTranslations("landing.capabilities");
  return (
    <section className={`${band.band} ${band.surface}`} aria-labelledby="capabilities-title">
      <div className={band.inner}>
        <header className={band.heading}>
          <p className={band.eyebrow}>{t("eyebrow")}</p>
          <h2 id="capabilities-title" className={band.title}>
            {t("title")}
          </h2>
        </header>
        <ul className={styles.grid}>
          {TILES.map((tile) => {
            const Glyph = tile.icon;
            return (
              <li key={tile.id} className={`${styles.tile} ${tile.image ? styles.large : ""}`}>
                <span className={styles.icon} aria-hidden>
                  <Glyph stroke={1.75} />
                </span>
                <h3 className={styles.title}>{t(`${tile.id}.title`)}</h3>
                <p className={styles.text}>{t(`${tile.id}.text`)}</p>
                {tile.image ? (
                  <div className={styles.shot}>
                    <ThemedImage
                      name={tile.image}
                      alt={t(`${tile.id as "roles" | "audit"}.alt`)}
                      width={1200}
                      height={680}
                    />
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
