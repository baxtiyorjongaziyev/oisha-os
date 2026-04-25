import { Injectable, NotFoundException, ForbiddenException, UnauthorizedException } from '@nestjs/common';
import * as argon2 from 'argon2';
import * as crypto from 'crypto';
import { PrismaService } from '../common/prisma.service';
import { CreateShareLinkDto } from './dto/create-share-link.dto';

@Injectable()
export class SharesService {
  constructor(private prisma: PrismaService) {}

  async create(callId: string, orgId: string, createdBy: string, dto: CreateShareLinkDto) {
    const call = await this.prisma.call.findUnique({ where: { id: callId } });
    if (!call) throw new NotFoundException('Call not found');
    if (call.orgId !== orgId) throw new ForbiddenException();

    const rawToken = crypto.randomBytes(32).toString('base64url');
    // SHA-256 hash stored in DB — raw token only lives in URL fragment
    const tokenHash = crypto.createHash('sha256').update(rawToken).digest('hex');
    const passwordHash = dto.password ? await argon2.hash(dto.password) : null;
    const expiresAt = new Date(Date.now() + (dto.expiresInDays ?? 30) * 86_400_000);

    const link = await this.prisma.shareLink.create({
      data: {
        callId,
        orgId,
        createdBy,
        tokenHash,
        expiresAt,
        passwordHash,
        maskCustomerName: dto.maskCustomerName ?? false,
      },
    });

    return { id: link.id, token: rawToken, expiresAt };
  }

  async revoke(linkId: string, orgId: string) {
    const link = await this.prisma.shareLink.findUnique({ where: { id: linkId } });
    if (!link) throw new NotFoundException('Share link not found');
    if (link.orgId !== orgId) throw new ForbiddenException();
    return this.prisma.shareLink.update({ where: { id: linkId }, data: { revokedAt: new Date() } });
  }

  async listByCall(callId: string, orgId: string) {
    const call = await this.prisma.call.findUnique({ where: { id: callId } });
    if (!call || call.orgId !== orgId) throw new ForbiddenException();
    return this.prisma.shareLink.findMany({
      where: { callId },
      select: { id: true, expiresAt: true, revokedAt: true, accessCount: true, maskCustomerName: true, createdAt: true },
      orderBy: { createdAt: 'desc' },
    });
  }

  async resolvePublic(rawToken: string, password?: string) {
    const tokenHash = crypto.createHash('sha256').update(rawToken).digest('hex');
    const link = await this.prisma.shareLink.findUnique({
      where: { tokenHash },
      include: {
        call: {
          include: {
            transcript: { orderBy: { seq: 'asc' } },
            scorecard: true,
          },
        },
      },
    });

    if (!link) throw new NotFoundException('Share link not found');
    if (link.revokedAt) throw new ForbiddenException('Link revoked');
    if (link.expiresAt < new Date()) throw new ForbiddenException('Link expired');

    if (link.passwordHash) {
      if (!password) throw new UnauthorizedException('Password required');
      const valid = await argon2.verify(link.passwordHash, password);
      if (!valid) throw new UnauthorizedException('Incorrect password');
    }

    await this.prisma.shareLink.update({
      where: { id: link.id },
      data: { accessCount: { increment: 1 } },
    });

    const { call } = link;
    return {
      call: {
        id: call.id,
        customerName: link.maskCustomerName ? null : call.customerName,
        direction: call.direction,
        language: call.language,
        durationSec: call.durationSec,
        createdAt: call.createdAt,
        transcript: call.transcript,
        scorecard: call.scorecard,
      },
    };
  }
}
