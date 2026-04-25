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
      console.log(`Received placeholder job ${job.name}`);
    },
    { connection }
  );
}
