// Title cards drawn by the web app itself (its fonts and colours) and the
// ffmpeg cut that joins cards and recorded scenes with short cross-fades.
import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { BASE } from "../runner.mjs";
import { FFMPEG } from "../landing/media.mjs";

const run = promisify(execFile);
const FPS = 30;
const FADE = 0.4;

function escape(text) {
  return text.replace(/[&<>"]/g, (char) => `&#${char.charCodeAt(0)};`);
}

/**
 * The card's markup. Sizes follow the frame's width, larger on a vertical
 * frame, so one card reads well in both formats.
 */
function cardHtml({ eyebrow, title, note, brand }) {
  const mark = `<span class="mark">Сноска</span><sup>1</sup>`;
  return `
    <style>
      .card { --unit: 1vw; position: fixed; inset: 0; display: grid; align-content: center;
        gap: calc(var(--unit) * 2.2); padding: 0 8vw; background: var(--color-canvas);
        color: var(--color-text); font-family: var(--font-ui); }
      @media (orientation: portrait) { .card { --unit: 1.7vw; } }
      .card .mark { font-family: var(--font-document); font-weight: 600; }
      .card sup { margin-inline-start: .08em; color: var(--color-ink); font-size: .55em; }
      .corner { position: absolute; inset-block-start: 6vw; inset-inline-start: 8vw;
        font-size: calc(var(--unit) * 3.2); }
      .eyebrow { margin: 0; color: var(--color-ink); font-family: var(--font-code);
        font-size: calc(var(--unit) * 2.6); }
      .title { margin: 0; font-size: calc(var(--unit) * 6.4); font-weight: 600;
        letter-spacing: -0.02em; line-height: 1.05; }
      .brand .title { font-size: calc(var(--unit) * 11); }
      .note { margin: 0; max-width: 62ch; color: var(--color-text-secondary);
        font-size: calc(var(--unit) * 3); line-height: 1.35; }
    </style>
    <main class="card ${brand ? "brand" : ""}">
      ${brand ? "" : `<div class="corner">${mark}</div>`}
      ${eyebrow ? `<p class="eyebrow">${escape(eyebrow)}</p>` : ""}
      <h1 class="title">${brand ? mark : escape(title)}</h1>
      <p class="note">${escape(note)}</p>
    </main>`;
}

/** Renders a card to a PNG at the format's size. */
export async function renderCard(browser, format, card, out) {
  const context = await browser.newContext({
    viewport: format.viewport,
    deviceScaleFactor: format.scale,
    colorScheme: "light",
  });
  await context.addCookies([{ name: "footnote_theme", value: "light", url: BASE }]);
  const page = await context.newPage();
  // A public page of the app: its stylesheet carries the fonts and tokens.
  await page.goto(`${BASE}/how-we-check`, { waitUntil: "networkidle" });
  await page.evaluate((html) => {
    document.body.innerHTML = html;
  }, cardHtml(card));
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: out });
  await context.close();
}

/**
 * Joins the pieces into a silent H.264 film of `width`×`height`. A piece is
 * a card `{ image, duration }` or a scene `{ video, start, duration, longest }`;
 * a scene longer than `longest` seconds is sped up to that length.
 */
export async function compose(pieces, out, { width, height }) {
  const inputs = [];
  const filters = [];
  const lengths = [];
  pieces.forEach((piece, index) => {
    const frame = `scale=${width}:${height}:flags=lanczos,setsar=1,format=yuv420p`;
    // xfade needs a constant frame rate: fps goes after the timing is set.
    const pace = `fps=${FPS},settb=AVTB`;
    if (piece.image) {
      inputs.push("-loop", "1", "-framerate", String(FPS), "-t", String(piece.duration));
      inputs.push("-i", piece.image);
      filters.push(`[${index}:v]${frame},setpts=PTS-STARTPTS,${pace}[p${index}]`);
      lengths.push(piece.duration);
      return;
    }
    const length = piece.longest ? Math.min(piece.duration, piece.longest) : piece.duration;
    const factor = (length / piece.duration).toFixed(4);
    inputs.push("-ss", piece.start.toFixed(2), "-t", piece.duration.toFixed(2), "-i", piece.video);
    filters.push(`[${index}:v]${frame},setpts=(PTS-STARTPTS)*${factor},${pace}[p${index}]`);
    lengths.push(length);
  });
  let previous = "p0";
  let offset = 0;
  for (let index = 1; index < pieces.length; index += 1) {
    offset += lengths[index - 1] - FADE;
    const label = index === pieces.length - 1 ? "out" : `x${index}`;
    filters.push(
      `[${previous}][p${index}]xfade=transition=fade:duration=${FADE}:offset=${offset.toFixed(3)}[${label}]`,
    );
    previous = label;
  }
  await run(
    FFMPEG,
    [
      "-y",
      "-v",
      "error",
      ...inputs,
      "-filter_complex",
      filters.join(";"),
      "-map",
      `[${previous}]`,
      "-an",
      "-c:v",
      "libx264",
      "-preset",
      "slow",
      "-crf",
      "22",
      "-pix_fmt",
      "yuv420p",
      "-movflags",
      "+faststart",
      out,
    ],
    { maxBuffer: 16 * 1024 * 1024 },
  );
  return lengths.reduce((sum, length) => sum + length, 0) - FADE * (pieces.length - 1);
}

/** A frame of the film as a WebP poster. */
export async function poster(film, at, out) {
  await run(FFMPEG, [
    "-y",
    "-v",
    "error",
    "-ss",
    String(at),
    "-i",
    film,
    "-frames:v",
    "1",
    "-c:v",
    "libwebp",
    "-quality",
    "85",
    out,
  ]);
}
