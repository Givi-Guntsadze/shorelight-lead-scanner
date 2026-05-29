const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

async function main() {
  const deviceCount = 26;
  const scansPerDevice = 5;
  const scanIntervalMs = 1000;
  const maxDrainMs = 720000;
  const urlBase = "http://127.0.0.1:8765/index.html";
  const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
  const scriptUrl = "https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js";
  const mockScript = `
    window.Html5Qrcode = class Html5Qrcode {
      constructor() {}
      async start() { return; }
      async stop() { return; }
      async clear() { return; }
    };
  `;

  const browser = await chromium.launch({
    headless: true,
    executablePath: chromePath,
  });
  const contexts = [];

  const setupDevice = async (deviceNumber) => {
    const context = await browser.newContext();
    contexts.push(context);
    await context.route(scriptUrl, route =>
      route.fulfill({
        status: 200,
        contentType: "application/javascript",
        body: mockScript,
      }),
    );

    const page = await context.newPage();
    const uni = `DEVICE${String(deviceNumber).padStart(2, "0")}`;
    await page.goto(`${urlBase}?uni=${uni}`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => typeof onScanSuccess === "function" && typeof sync === "function");
    await page.evaluate(deviceNumber => {
      localStorage.clear();
      scanQueue = [];
      saveQueue();
      document.getElementById("scans-list").innerHTML =
        '<li class="empty-state">No scans yet. Point camera at a QR code.</li>';
      updateUI();

      const nativeFetch = window.fetch.bind(window);
      window.__testLog = { deviceNumber, scans: [], fetches: [] };
      window.fetch = async (...args) => {
        const started = Date.now();
        const entry = { url: String(args[0]), started_at: new Date(started).toISOString() };
        try {
          const response = await nativeFetch(...args);
          entry.status = response.status;
          entry.ok = response.ok;
          entry.elapsed_ms = Date.now() - started;
          try {
            entry.body = await response.clone().json();
          } catch (error) {
            entry.body_error = String(error);
          }
          window.__testLog.fetches.push(entry);
          return response;
        } catch (error) {
          entry.error = String(error);
          entry.elapsed_ms = Date.now() - started;
          window.__testLog.fetches.push(entry);
          throw error;
        }
      };
    }, deviceNumber);

    return { deviceNumber, uni, page };
  };

  try {
    const devices = await Promise.all(
      Array.from({ length: deviceCount }, (_, index) => setupDevice(index + 1)),
    );

    await Promise.all(
      devices.map(({ deviceNumber, page }) =>
        page.evaluate(
          async ({ deviceNumber, scansPerDevice, scanIntervalMs }) => {
            for (let iteration = 1; iteration <= scansPerDevice; iteration += 1) {
              const uuid = `MULTIDEVICE_${String(deviceNumber).padStart(2, "0")}_${iteration}_${Date.now()}_${Math.floor(Math.random() * 10000)}`;
              window.__testLog.scans.push({
                deviceNumber,
                iteration,
                uuid,
                at: new Date().toISOString(),
              });
              onScanSuccess(uuid);
              if (iteration < scansPerDevice) {
                await new Promise(resolve => setTimeout(resolve, scanIntervalMs));
              }
            }
          },
          { deviceNumber, scansPerDevice, scanIntervalMs },
        ),
      ),
    );

    const drainStartedAt = Date.now();
    let completedDrain = false;
    while (Date.now() - drainStartedAt < maxDrainMs) {
      const states = await Promise.all(
        devices.map(({ page }) => page.evaluate(() => ({ pending: getPendingCount(), syncing: isSyncing }))),
      );
      if (states.every(state => state.pending === 0 && !state.syncing)) {
        completedDrain = true;
        break;
      }
      await devices[0].page.waitForTimeout(1000);
    }

    const perDevice = await Promise.all(
      devices.map(({ deviceNumber, uni, page }) =>
        page.evaluate(({ deviceNumber, uni }) => {
          const queue = JSON.parse(localStorage.getItem("traqrecord_scan_queue") || "[]");
          const fetches = window.__testLog.fetches || [];
          const scans = window.__testLog.scans || [];
          const busyAttempts = fetches.filter(
            item =>
              item.body?.result === "error" &&
              String(item.body?.message || "").toLowerCase().includes("server busy"),
          ).length;
          const successAttempts = fetches.filter(item => item.body?.result === "success").length;
          const networkFailures = fetches.filter(item => item.error).length;
          const counts = queue.reduce((acc, item) => {
            acc[item.id] = (acc[item.id] || 0) + 1;
            return acc;
          }, {});

          return {
            deviceNumber,
            uni,
            scans_enqueued: scans.length,
            fetch_attempts: fetches.length,
            success_attempts: successAttempts,
            busy_attempts: busyAttempts,
            network_failures: networkFailures,
            synced_scans: queue.filter(item => item.status === "synced").length,
            pending_scans: queue.filter(item => item.status === "pending").length,
            avg_fetch_ms: fetches.length
              ? Math.round(fetches.reduce((sum, item) => sum + (item.elapsed_ms || 0), 0) / fetches.length)
              : 0,
            max_fetch_ms: fetches.length
              ? Math.max(...fetches.map(item => item.elapsed_ms || 0))
              : 0,
            duplicate_queue_ids: Object.values(counts).filter(count => count > 1).length,
          };
        }, { deviceNumber, uni }),
      ),
    );

    const aggregate = perDevice.reduce(
      (acc, item) => {
        acc.scans_enqueued += item.scans_enqueued;
        acc.fetch_attempts += item.fetch_attempts;
        acc.success_attempts += item.success_attempts;
        acc.busy_attempts += item.busy_attempts;
        acc.network_failures += item.network_failures;
        acc.synced_scans += item.synced_scans;
        acc.pending_scans += item.pending_scans;
        acc.duplicate_queue_ids += item.duplicate_queue_ids;
        acc.max_fetch_ms = Math.max(acc.max_fetch_ms, item.max_fetch_ms);
        return acc;
      },
      {
        scans_enqueued: 0,
        fetch_attempts: 0,
        success_attempts: 0,
        busy_attempts: 0,
        network_failures: 0,
        synced_scans: 0,
        pending_scans: 0,
        duplicate_queue_ids: 0,
        max_fetch_ms: 0,
      },
    );

    const devicesWithFetches = perDevice.filter(item => item.fetch_attempts > 0);
    aggregate.avg_fetch_ms = devicesWithFetches.length
      ? Math.round(
          devicesWithFetches.reduce((sum, item) => sum + item.avg_fetch_ms, 0) / devicesWithFetches.length,
        )
      : 0;

    const report = {
      test: {
        device_count: deviceCount,
        scans_per_device: scansPerDevice,
        scan_window_seconds: scansPerDevice,
        total_planned_scans: deviceCount * scansPerDevice,
        drain_window_seconds: Math.round((Date.now() - drainStartedAt) / 1000),
        completed_drain: completedDrain,
      },
      aggregate,
      per_device: perDevice,
    };

    const reportPath = path.join(process.cwd(), "output", "playwright", "multi_device_exact_report.json");
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    console.log(`REPORT_PATH=${reportPath}`);
    console.log(JSON.stringify(report, null, 2));
  } finally {
    await Promise.all(contexts.map(context => context.close()));
    await browser.close();
  }
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
