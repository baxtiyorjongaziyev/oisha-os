import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../common/prisma.service';

@Injectable()
export class UsersService {
  constructor(private prisma: PrismaService) {}

  async findById(id: string) {
    const user = await this.prisma.user.findUnique({ where: { id } });
    if (!user) throw new NotFoundException('User not found');
    return user;
  }

  async findByOrgId(orgId: string) {
    return this.prisma.user.findMany({ where: { orgId }, orderBy: { createdAt: 'asc' } });
  }

  async updateLocale(id: string, locale: 'uz' | 'ru') {
    return this.prisma.user.update({ where: { id }, data: { locale } });
  }

  async remove(id: string) {
    await this.prisma.user.delete({ where: { id } });
  }
}
