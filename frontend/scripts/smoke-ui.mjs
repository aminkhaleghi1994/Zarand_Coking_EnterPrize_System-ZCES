import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const frontendDir = dirname(scriptDir);
const repoRoot = dirname(frontendDir);

const BASE_URL = (process.env.SMOKE_FRONTEND_URL ?? "http://127.0.0.1:3000").replace(/\/+$/, "");
const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
].filter(Boolean);

function readAdminCredentials() {
  const envPath = join(repoRoot, "backend", ".env");
  if (!existsSync(envPath)) {
    throw new Error(`backend/.env not found at ${envPath}`);
  }
  const vars = new Map();
  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const match = /^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/.exec(line);
    if (match) vars.set(match[1], match[2]);
  }
  const email = vars.get("INITIAL_ADMIN_EMAIL");
  const password = vars.get("INITIAL_ADMIN_PASSWORD");
  if (!email || !password) {
    throw new Error("INITIAL_ADMIN_EMAIL / INITIAL_ADMIN_PASSWORD missing in backend/.env");
  }
  return { email, password };
}

const failures = [];

function check(name, ok, detail = "") {
  const suffix = detail ? ` :: ${detail}` : "";
  if (ok) {
    console.log(`PASS  ${name}`);
  } else {
    console.log(`FAIL  ${name}${suffix}`);
    failures.push(`${name}${suffix}`);
  }
}

const browser = await puppeteer.launch({
  headless: true,
  executablePath: CHROME_CANDIDATES.find((p) => existsSync(p)),
  args: ["--disable-extensions", "--window-size=1440,900"],
  defaultViewport: { width: 1440, height: 900 },
});

try {
  const page = await browser.newPage();
  const consoleErrors = [];
  const assetFailures = [];
  const HYDRATION_ERROR_PATTERN = /hydrat|did not match|Encountered a script tag|recover/i;

  page.on("console", (message) => {
    const text = message.text();
    if (message.type() === "error" || HYDRATION_ERROR_PATTERN.test(text)) {
      consoleErrors.push(text);
    }
  });
  page.on("pageerror", (error) => consoleErrors.push(`pageerror: ${error.message}`));
  page.on("response", (response) => {
    if (response.url().includes("/_next/") && response.status() >= 400) {
      assetFailures.push(`${response.status()} ${response.url()}`);
    }
  });
  page.on("requestfailed", (request) => {
    if (request.url().includes("/_next/")) {
      assetFailures.push(`${request.failure()?.errorText ?? "failed"} ${request.url()}`);
    }
  });

  const loginUrl = `${BASE_URL}/fa/login`;
  await page.goto(`${loginUrl}?email=test%40example.ir&password=dummy-password-1`, {
    waitUntil: "networkidle2",
    timeout: 90_000,
  });
  await page.goto(loginUrl, { waitUntil: "networkidle2", timeout: 90_000 });

  check("login page renders", (await page.$("#login-email")) !== null);

  const themeToggle = await page.$("button[title]");
  check("theme toggle button found", themeToggle !== null);
  if (themeToggle) {
    const isDark = () => page.evaluate(() => document.documentElement.classList.contains("dark"));
    const initial = await isDark();

    await themeToggle.click();
    await new Promise((resolve) => setTimeout(resolve, 300));
    const afterFirst = await isDark();
    check("theme toggles on click", afterFirst !== initial, `initial=${initial} after=${afterFirst}`);

    await page.reload({ waitUntil: "networkidle2" });
    const persisted = await isDark();
    check("theme choice persists after reload", persisted === afterFirst, `after=${afterFirst} persisted=${persisted}`);

    const toggleAfterReload = await page.$("button[title]");
    await toggleAfterReload.click();
    await new Promise((resolve) => setTimeout(resolve, 300));
    const afterSecond = await isDark();
    check("theme toggles back", afterSecond === initial, `expected=${initial} after=${afterSecond}`);
  }

  const { email, password } = readAdminCredentials();
  await page.type("#login-email", email);
  await page.type("#login-password", password);
  await Promise.all([
    page.waitForFunction(
      () => window.location.pathname !== "/fa/login",
      { polling: 250, timeout: 30_000 },
    ),
    page.click("button[type=submit]"),
  ]);

  const finalUrl = new URL(page.url());
  check(
    "login redirects without leaking credentials in URL",
    finalUrl.pathname !== "/fa/login" || (finalUrl.search === "" && !finalUrl.searchParams.has("email")),
    page.url(),
  );
  check("login lands on locale home", finalUrl.pathname === "/fa", page.url());

  const cookies = await page.cookies();
  const hasSession = cookies.some((cookie) => cookie.name === "zces_at" && cookie.value.length > 10);
  check("session cookie zces_at set", hasSession);

  check("no /_next asset failures (hydration JS reachable)", assetFailures.length === 0, assetFailures.join(" | "));
  check("no console/page errors", consoleErrors.length === 0, consoleErrors.join(" | "));
} finally {
  await browser.close();
}

console.log("");
if (failures.length > 0) {
  console.log(`UI SMOKE TEST FAILED: ${failures.length} check(s) failed.`);
  process.exit(1);
}
console.log("UI SMOKE TEST PASSED: all checks green.");
