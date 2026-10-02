// Captures the screens of a milestone in three viewports and both themes.
//
//   node e2e/screenshots.mjs                 milestone 2 into docs/screenshots/m2
//   MILESTONE=m1 node e2e/screenshots.mjs    milestone 1 into docs/screenshots/m1
//   SCREENS=result node e2e/screenshots.mjs  only screens whose name contains "result"
//   SCREENS='!queued' node e2e/...           all but those (several: SCREENS=result,!queued)
//
// Demo credentials are read from the project's seed file.
import { capture } from "./runner.mjs";

const milestone = process.env.MILESTONE ?? "m2";
const { SCREENS, USERS } = await import(`./screens/${milestone}.mjs`);

await capture({
  screens: SCREENS,
  users: USERS,
  outDir: process.env.OUT_DIR ?? `docs/screenshots/${milestone}`,
});
