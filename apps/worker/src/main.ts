import { createServer } from "node:http";
import { Worker } from "bullmq";
import IORedis from "ioredis";

const port = Number(process.env.WORKER_HEALTH_PORT ?? 3002);
const redisUrl = process.env.REDIS_URL ?? "redis://localhost:6379";

const server = createServer((_req, res) => {
  res.writeHead(200, { "content-type": "application/json" });
  res.end(
    JSON.stringify({
      status: "ok",
      service: "salescoach-worker",
      checkedAt: new Date().toISOString()
    })
  );
});

server.listen(port, "0.0.0.0", () => {
  console.log(`SalesCoach worker health listening on ${port}`);
});

if (process.env.START_WORKER !== "false") {
  const connection = new IORedis(redisUrl, { maxRetriesPerRequest: null });

  new Worker(
    "salescoach-jobs",
    async (job) => {
      const apiUrl = process.env.OISHA_API_URL ?? "http://127.0.0.1:8080";
      const secret = process.env.AMOCRM_CRON_SECRET ?? process.env.OISHA_API_SECRET;
      if (job.name !== "amocrm-call-backfill") {
        throw new Error(`Unsupported salescoach job: ${job.name}`);
      }
      if (!secret) {
        throw new Error("AMOCRM_CRON_SECRET or OISHA_API_SECRET is required");
      }
      const limit = Number(job.data?.limit ?? 30);
      const response = await fetch(
        `${apiUrl}/api/amocrm-call-analysis/run?wait=true&limit=${limit}`,
        { method: "POST", headers: { Authorization: `Bearer ${secret}` } }
      );
      if (!response.ok) {
        throw new Error(`Oisha call backfill failed: HTTP ${response.status}`);
      }
      return response.json();
    },
    { connection }
  );
}
