module.exports = {
  apps: [
    {
      name: "qgen-compose-boot",
      cwd: "/home/admin/serv/vquest",
      script: "/usr/bin/docker",
      args: "compose --env-file .env.local up -d --build",
      interpreter: "none",
      autorestart: false,
      time: true
    },
    {
      name: "qgen-api",
      cwd: "/home/admin/serv/vquest/backend",
      script: "/home/admin/serv/vquest/backend/.venv/bin/python",
      args: "-m uvicorn app.main:app --host 0.0.0.0 --port 8000 --env-file .env.local",
      interpreter: "none",
      out_file: "/home/admin/serv/vquest/logs/api.log",
      error_file: "/home/admin/serv/vquest/logs/api.log",
      autorestart: true,
      max_restarts: 10,
      time: true
    },
    {
      name: "qgen-worker",
      cwd: "/home/admin/serv/vquest/backend",
      script: "/home/admin/serv/vquest/backend/.venv/bin/python",
      args: "-m app.workers.runner",
      interpreter: "none",
      out_file: "/home/admin/serv/vquest/logs/worker.log",
      error_file: "/home/admin/serv/vquest/logs/worker.log",
      autorestart: true,
      max_restarts: 10,
      time: true
    }
  ]
};
