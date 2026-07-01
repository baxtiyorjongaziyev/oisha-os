import {
  ExecutionContext,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from '../prisma.service';

/**
 * Machine-to-machine + JWT auth guard.
 *
 * - If `Authorization: Bearer <SERVICE_TOKEN>` matches the configured
 *   `SERVICE_TOKEN` env var, the request is treated as an internal service
 *   call (oisha-os bridge, MCP server) and `request.user` is populated with
 *   the service organization's OWNER identity.
 * - Otherwise it falls back to the standard passport-jwt strategy, so the web
 *   frontend keeps working unchanged.
 *
 * Service auth is DISABLED unless `SERVICE_TOKEN` is set (empty by default),
 * so this adds no bypass in deployments that don't opt in.
 */
@Injectable()
export class ServiceOrJwtAuthGuard extends AuthGuard('jwt') {
  private cachedIdentity:
    | { id: string; orgId: string; email: string; role: string }
    | null = null;

  constructor(
    private readonly cfg: ConfigService,
    private readonly prisma: PrismaService,
  ) {
    super();
  }

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const req = context.switchToHttp().getRequest();
    const authHeader: string = req.headers?.authorization ?? '';
    const serviceToken = this.cfg.get<string>('SERVICE_TOKEN');

    if (serviceToken && authHeader === `Bearer ${serviceToken}`) {
      req.user = await this.resolveServiceIdentity();
      return true;
    }

    return super.canActivate(context) as Promise<boolean>;
  }

  private async resolveServiceIdentity() {
    if (this.cachedIdentity) return this.cachedIdentity;

    const configuredOrgId = this.cfg.get<string>('SERVICE_ORG_ID');
    const org = configuredOrgId
      ? await this.prisma.organization.findUnique({ where: { id: configuredOrgId } })
      : await this.prisma.organization.findFirst({ orderBy: { createdAt: 'asc' } });

    if (!org) {
      throw new UnauthorizedException(
        'Service auth: no organization found. Register an org or set SERVICE_ORG_ID.',
      );
    }

    const owner = await this.prisma.user.findFirst({
      where: { orgId: org.id },
      orderBy: { createdAt: 'asc' },
    });

    this.cachedIdentity = {
      id: owner?.id ?? `service:${org.id}`,
      orgId: org.id,
      email: owner?.email ?? 'service@salescoach.ai',
      role: 'OWNER',
    };
    return this.cachedIdentity;
  }
}
