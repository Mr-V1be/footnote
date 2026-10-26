// Recording helpers shared by the landing's clips and the product video:
// a context that records the screen, and ffmpeg to cut and encode it.
import { execFile } from "node:child_process";
import { mkdir, readdir, rm } from "node:fs/promises";
import { join } from "node:path";
import { promisify } from "node:util";

const run = promisify(execFile);
// The system's ffmpeg encodes H.264; Playwright's own build only writes VP8.
export const FFMPEG = process.env.FFMPEG ?? "/usr/bin/ffmpeg";

/**
 * A browser for recording. Headless Chromium's screencast ignores the
 * emulated device scale and captures CSS pixels; the browser-wide flag makes
 * the frames as sharp as a screenshot at `scale`.
 */
export function launchRecorder(chromium, scale = 2) {
  return chromium.launch({ args: ["--mute-audio", `--force-device-scale-factor=${scale}`] });
}

/**
 * Opens a context that records its screen into `dir`. Returns the page, a
 * `mark()` that notes when the part worth keeping starts and `elapsed()`
 * for scripts that keep several parts of one recording.
 */
export async function recording(
  browser,
  { viewport, scale = 1, theme, storageState, dir, mobile },
) {
  await rm(dir, { recursive: true, force: true });
  await mkdir(dir, { recursive: true });
  const context = await browser.newContext({
    viewport,
    deviceScaleFactor: scale,
    colorScheme: theme,
    storageState,
    isMobile: mobile,
    hasTouch: mobile,
    recordVideo: { dir, size: { width: viewport.width * scale, height: viewport.height * scale } },
  });
  await context.addCookies([
    { name: "footnote_theme", value: theme, url: process.env.WEB_URL ?? "http://localhost:46300" },
  ]);
  const opened = Date.now();
  const page = await context.newPage();
  let start = 0;
  return {
    page,
    context,
    mark: () => {
      start = (Date.now() - opened) / 1000;
    },
    /** Seconds since the recording started. */
    elapsed: () => (Date.now() - opened) / 1000,
    finish: async () => {
      const end = (Date.now() - opened) / 1000;
      await context.close();
      const [file] = (await readdir(dir)).filter((name) => name.endsWith(".webm"));
      return { file: join(dir, file), start, duration: end - start };
    },
  };
}

/**
 * A silent H.264 loop and a WebP poster from a recording. The poster is the
 * first frame, or the last when the clip ends on what it is about (an answer).
 */
export async function encodeLoop({ file, start, duration }, out, { width, poster = "start" }) {
  const filters = `scale=${width}:-2:flags=lanczos,fps=30`;
  await run(FFMPEG, [
    "-y",
    "-v",
    "error",
    "-ss",
    String(start),
    "-t",
    String(duration),
    "-i",
    file,
    "-vf",
    filters,
    "-an",
    "-c:v",
    "libx264",
    "-preset",
    "slow",
    "-crf",
    "26",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    `${out}.mp4`,
  ]);
  await run(FFMPEG, [
    "-y",
    "-v",
    "error",
    "-ss",
    String(poster === "end" ? start + duration - 0.4 : start + 0.2),
    "-i",
    file,
    "-frames:v",
    "1",
    "-vf",
    `scale=${width}:-2:flags=lanczos`,
    "-c:v",
    "libwebp",
    "-quality",
    "82",
    `${out}.webp`,
  ]);
}

/** A still as WebP from a PNG screenshot. */
export async function encodeStill(png, out, { width }) {
  await run(FFMPEG, [
    "-y",
    "-v",
    "error",
    "-i",
    png,
    "-vf",
    `scale=${width}:-2:flags=lanczos`,
    "-c:v",
    "libwebp",
    "-quality",
    "82",
    `${out}.webp`,
  ]);
}

export async function pause(page, ms) {
  await page.waitForTimeout(ms);
}

/** Scrolls an element (or the page) smoothly by `distance` pixels over `ms`. */
export async function glide(page, distance, ms, selector = null) {
  await page.evaluate(
    async ({ distance, ms, selector }) => {
      const target = selector ? document.querySelector(selector) : document.scrollingElement;
      const from = target.scrollTop;
      const started = performance.now();
      await new Promise((done) => {
        const step = (now) => {
          const t = Math.min((now - started) / ms, 1);
          const eased = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
          target.scrollTop = from + distance * eased;
          if (t < 1) requestAnimationFrame(step);
          else done();
        };
        requestAnimationFrame(step);
      });
    },
    { distance, ms, selector },
  );
}
