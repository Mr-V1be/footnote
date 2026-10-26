// The product video, silent, 45–75 s, in two cuts: 1920×1080 for the case
// page and 1080×1920 for phones. Plays the scenes on the demo stand with
// headless Chromium (sound muted), then joins them with title cards.
//   node e2e/video/record.mjs               both cuts
//   FORMATS=wide node e2e/video/record.mjs  one of them
// Needs the stand with the seed and its checks (make demo-refresh); the
// stand returns to its seed afterwards (restoreStand).
import { mkdir, rm } from "node:fs/promises";
import { resolve } from "node:path";

import { chromium } from "playwright";

import { ROOT, credentials, restoreStand, signIn } from "../runner.mjs";
import { launchRecorder, recording } from "../landing/media.mjs";
import { compose, poster, renderCard } from "./compose.mjs";
import { INTRO, OUTRO, SCENES, uploadTitle } from "./scenes.mjs";

const OUT = resolve(ROOT, "docs/case/video");
const WORK = resolve(ROOT, ".run/video");
const LAWYER = "polyakova@zarya.example";
const CARD_SECONDS = 2;
const INTRO_SECONDS = 3.2;
const END_SECONDS = 3.4;

const FORMATS = {
  wide: {
    viewport: { width: 1280, height: 720 },
    scale: 1.5,
    size: { width: 1920, height: 1080 },
    narrow: false,
    file: "footnote-1920x1080",
  },
  vertical: {
    viewport: { width: 360, height: 640 },
    scale: 3,
    size: { width: 1080, height: 1920 },
    narrow: true,
    file: "footnote-1080x1920",
  },
};

function wanted(name) {
  const filter = (process.env.FORMATS ?? "").split(",").filter(Boolean);
  return filter.length === 0 || filter.includes(name);
}

async function film(name, format, state) {
  const browser = await launchRecorder(chromium, format.scale);
  const work = resolve(WORK, name);
  await mkdir(work, { recursive: true });
  const card = async (id, content, eyebrow) => {
    const image = resolve(work, `card-${id}.png`);
    await renderCard(browser, format, { ...content, eyebrow }, image);
    return image;
  };
  const pieces = [
    { image: await card("intro", { ...INTRO, brand: true }), duration: INTRO_SECONDS },
  ];

  const take = await recording(browser, {
    viewport: format.viewport,
    scale: format.scale,
    theme: "light",
    storageState: state,
    dir: resolve(work, "screen"),
    mobile: format.narrow,
  });
  const parts = [];
  let begun = 0;
  const marks = {
    begin: () => {
      begun = take.elapsed();
    },
    end: () => {
      parts.push({ start: begun, duration: take.elapsed() - begun });
    },
  };
  const context = { title: uploadTitle(), narrow: format.narrow };
  for (const scene of SCENES) {
    await scene.run(take.page, marks, context);
    console.log(`${name}: ${scene.id} ${parts.at(-1).duration.toFixed(1)} s`);
  }
  const { file } = await take.finish();
  for (const [index, scene] of SCENES.entries()) {
    const eyebrow = `${index + 1} / ${SCENES.length}`;
    pieces.push({ image: await card(scene.id, scene.card, eyebrow), duration: CARD_SECONDS });
    pieces.push({ video: file, ...parts[index], longest: scene.longest });
  }
  pieces.push({ image: await card("outro", OUTRO), duration: END_SECONDS });
  await browser.close();

  const out = resolve(OUT, `${format.file}.mp4`);
  const length = await compose(pieces, out, format.size);
  await poster(out, INTRO_SECONDS + CARD_SECONDS + 4, resolve(OUT, `${format.file}.webp`));
  console.log(`${name}: ${out} ${length.toFixed(1)} s`);
}

await mkdir(OUT, { recursive: true });
const passwords = await credentials();
const signer = await chromium.launch({ args: ["--mute-audio"] });
const state = await signIn(signer, LAWYER, passwords.get(LAWYER));
await signer.close();
for (const [name, format] of Object.entries(FORMATS)) {
  if (wanted(name)) await film(name, format, state);
}
await rm(WORK, { recursive: true, force: true });
await restoreStand();
