module.exports = {
  apps: [
    {
      name: "salescoach-api",
      script: "pnpm",
      args: "run start --filter @salescoach/api",
      env: {
        NODE_ENV: "production",
        PORT: 3001
      }
    },
    {
      name: "salescoach-web",
      script: "pnpm",
      args: "run start --filter @salescoach/web",
      env: {
        NODE_ENV: "production",
        PORT: 3000
      }
    },
    {
      name: "salescoach-worker",
      script: "pnpm",
      args: "run start --filter @salescoach/worker",
      env: {
        NODE_ENV: "production",
        WORKER_HEALTH_PORT: 3002
      }
    }
  ]
};
