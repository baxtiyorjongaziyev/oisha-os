import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../common/prisma.service';

@Injectable()
export class OrganizationsService {
  constructor(private prisma: PrismaService) {}

  async findById(id: string) {
    const org = await this.prisma.organization.findUnique({ where: { id } });
    if (!org) throw new NotFoundException('Organization not found');
    return org;
  }

  async getUsage(orgId: string) {
    const now = new Date();
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
    const [org, callsThisMonth] = await Promise.all([
      this.findById(orgId),
      this.prisma.call.count({ where: { orgId, createdAt: { gte: startOfMonth } } }),
    ]);
    return { plan: org.plan, monthlyCallQuota: org.monthlyCallQuota, used: callsThisMonth };
  }
}
