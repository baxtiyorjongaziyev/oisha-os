import { Injectable, UnauthorizedException, ConflictException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import * as argon2 from 'argon2';
import { PrismaService } from '../common/prisma.service';
import { UsersService } from '../users/users.service';
import { RegisterDto } from './dto/register.dto';

@Injectable()
export class AuthService {
  constructor(
    private prisma: PrismaService,
    private jwtService: JwtService,
    private cfg: ConfigService,
    private usersService: UsersService,
  ) {}

  async validateLocal(email: string, password: string) {
    const user = await this.prisma.user.findUnique({ where: { email } });
    if (!user?.passwordHash) throw new UnauthorizedException();
    const valid = await argon2.verify(user.passwordHash, password);
    if (!valid) throw new UnauthorizedException();
    return user;
  }

  async register(dto: RegisterDto) {
    const existing = await this.prisma.user.findUnique({ where: { email: dto.email } });
    if (existing) throw new ConflictException('Email already registered');

    const org = await this.prisma.organization.create({
      data: { name: dto.orgName },
    });

    const passwordHash = await argon2.hash(dto.password);
    const user = await this.prisma.user.create({
      data: {
        orgId: org.id,
        email: dto.email,
        passwordHash,
        role: 'OWNER',
        locale: dto.locale ?? 'uz',
      },
    });

    return this.issueTokens(user);
  }

  async login(user: { id: string; orgId: string; email: string; role: string }) {
    return this.issueTokens(user);
  }

  async loginWithGoogle(profile: {
    googleId: string;
    email: string;
    displayName: string;
  }) {
    let user = await this.prisma.user.findUnique({ where: { googleId: profile.googleId } });

    if (!user) {
      user = await this.prisma.user.findUnique({ where: { email: profile.email } });
      if (user) {
        user = await this.prisma.user.update({
          where: { id: user.id },
          data: { googleId: profile.googleId },
        });
      } else {
        const org = await this.prisma.organization.create({
          data: { name: `${profile.displayName}'s Org` },
        });
        user = await this.prisma.user.create({
          data: {
            orgId: org.id,
            email: profile.email,
            googleId: profile.googleId,
            role: 'OWNER',
          },
        });
      }
    }

    return this.issueTokens(user);
  }

  async refresh(token: string) {
    const tokenHash = await argon2.hash(token, { type: argon2.argon2id });
    const rt = await this.prisma.refreshToken.findUnique({ where: { tokenHash } });
    if (!rt || rt.revokedAt || rt.expiresAt < new Date()) {
      throw new UnauthorizedException('Refresh token invalid or expired');
    }
    const user = await this.prisma.user.findUniqueOrThrow({ where: { id: rt.userId } });
    await this.prisma.refreshToken.update({ where: { id: rt.id }, data: { revokedAt: new Date() } });
    return this.issueTokens(user);
  }

  async logout(refreshToken: string) {
    try {
      const tokenHash = await argon2.hash(refreshToken, { type: argon2.argon2id });
      await this.prisma.refreshToken.updateMany({
        where: { tokenHash },
        data: { revokedAt: new Date() },
      });
    } catch {}
  }

  private async issueTokens(user: { id: string; orgId: string; email: string; role: string }) {
    const payload = { sub: user.id, orgId: user.orgId, email: user.email, role: user.role };
    const accessToken = this.jwtService.sign(payload);

    const rawRefresh = crypto.randomUUID();
    const tokenHash = await argon2.hash(rawRefresh, { type: argon2.argon2id });
    const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000); // 30d

    await this.prisma.refreshToken.create({
      data: { userId: user.id, tokenHash, expiresAt },
    });

    return { accessToken, refreshToken: rawRefresh };
  }
}
