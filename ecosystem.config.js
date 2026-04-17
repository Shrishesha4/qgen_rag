module.exports = {
  apps: [
    {
      name: "qgen-compose-boot",
      cwd: "/Users/aadhi/Developer/work/vquest",
      script: "docker",
      args: "compose --env-file .env.local up -d --build",
      interpreter: "none",
      autorestart: false,
      time: true
    },
    {
      name: "qgen-api",
      cwd: "/Users/aadhi/Developer/work/vquest/backend",
      script: "/Users/aadhi/Developer/work/vquest/backend/.venv/bin/python",
      args: "-m uvicorn app.main:app --host 0.0.0.0 --port 8001 --env-file .env.local",
      interpreter: "none",
      out_file: "/Users/aadhi/Developer/work/vquest/logs/api.log",
      error_file: "/Users/aadhi/Developer/work/vquest/logs/api.log",
      autorestart: true,
      max_restarts: 10,
      time: true
    },
    {
      name: "qgen-worker",
      cwd: "/Users/aadhi/Developer/work/vquest/backend",
      script: "/Users/aadhi/Developer/work/vquest/backend/.venv/bin/python",
      args: "-m app.workers.runner",
      interpreter: "none",
      out_file: "/Users/aadhi/Developer/work/vquest/logs/worker.log",
      error_file: "/Users/aadhi/Developer/work/vquest/logs/worker.log",
      autorestart: true,
      max_restarts: 10,
      time: true,
      env_file: "/Users/aadhi/Developer/work/vquest/backend/.env.local"
    }
  ]
};
