# Code Mode sandbox image. Run with: --network none --read-only --cap-drop ALL (see bridge.build_command).
FROM node:24-slim
WORKDIR /app
COPY runner.mjs /app/runner.mjs
USER 65534:65534
# Container has no network, so script talks to host only via stdin/stdout JSON lines.
ENTRYPOINT ["node", "--permission", "--allow-fs-read=/app/runner.mjs", "--allow-fs-read=/work", "/app/runner.mjs"]
