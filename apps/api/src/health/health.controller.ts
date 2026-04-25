import { Controller, Get } from "@nestjs/common";
import type { HealthResponse } from "@salescoach/shared-types";

@Controller()
export class HealthController {
  @Get("healthz")
  healthz(): HealthResponse {
    return {
      status: "ok",
      service: "salescoach-api",
      checkedAt: new Date().toISOString()
    };
  }
}
