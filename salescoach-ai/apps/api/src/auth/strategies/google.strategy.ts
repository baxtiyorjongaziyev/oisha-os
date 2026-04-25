import { Injectable } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { Strategy, VerifyCallback } from 'passport-google-oauth20';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class GoogleStrategy extends PassportStrategy(Strategy, 'google') {
  constructor(cfg: ConfigService) {
    const clientID = cfg.get<string>('GOOGLE_CLIENT_ID') || 'placeholder';
    const clientSecret = cfg.get<string>('GOOGLE_CLIENT_SECRET') || 'placeholder';
    const callbackURL = cfg.get<string>('GOOGLE_CALLBACK_URL') ?? 'http://localhost:4000/v1/auth/google/callback';
    super({ clientID, clientSecret, callbackURL, scope: ['email', 'profile'] });
  }

  validate(
    _accessToken: string,
    _refreshToken: string,
    profile: any,
    done: VerifyCallback,
  ) {
    const { id, displayName, emails } = profile;
    done(null, { googleId: id, email: emails[0].value, displayName });
  }
}
