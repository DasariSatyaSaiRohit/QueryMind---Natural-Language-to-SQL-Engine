import {
  ConflictException,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcrypt';
import { UsersService } from '../users/users.service';
import { JwtPayload } from './jwt.strategy';

const BCRYPT_SALT_ROUNDS = 12;
const JWT_SECRET = process.env.JWT_SECRET || 'querymind-jwt-secret-change-in-production';

@Injectable()
export class AuthService {
  constructor(
    private readonly usersService: UsersService,
    private readonly jwtService: JwtService,
  ) {}

  async register(email: string, password: string) {
    const existing = await this.usersService.findByEmail(email);
    if (existing) {
      throw new ConflictException({ error: 'email_taken', message: 'An account with this email already exists' });
    }

    const passwordHash = await bcrypt.hash(password, BCRYPT_SALT_ROUNDS);
    const user = await this.usersService.create(email, passwordHash);

    return {
      user_id: user.user_id,
      email: user.email,
      created_at: user.created_at,
    };
  }

  async login(email: string, password: string) {
    const user = await this.usersService.findByEmail(email);
    if (!user) {
      throw new UnauthorizedException({ error: 'invalid_credentials', message: 'Email or password is incorrect.' });
    }

    const valid = await bcrypt.compare(password, user.password_hash);
    if (!valid) {
      throw new UnauthorizedException({ error: 'invalid_credentials', message: 'Email or password is incorrect.' });
    }

    const accessToken = this.issueAccessToken(user.user_id, user.email);
    const refreshToken = this.issueRefreshToken(user.user_id, user.email);

    return {
      access_token: accessToken,
      refresh_token: refreshToken,
      user: { user_id: user.user_id, email: user.email },
    };
  }

  async refresh(refreshToken: string) {
    let payload: JwtPayload;
    try {
      payload = this.jwtService.verify<JwtPayload>(refreshToken, { secret: JWT_SECRET });
    } catch {
      throw new UnauthorizedException({ error: 'invalid_token', message: 'Refresh token is invalid or expired' });
    }

    if (payload.type !== 'refresh') {
      throw new UnauthorizedException({ error: 'invalid_token', message: 'Not a refresh token' });
    }

    const user = await this.usersService.findById(payload.sub);
    if (!user) {
      throw new UnauthorizedException({ error: 'user_not_found', message: 'User no longer exists' });
    }

    return { access_token: this.issueAccessToken(user.user_id, user.email) };
  }

  private issueAccessToken(userId: string, email: string): string {
    const payload: JwtPayload = { sub: userId, email, type: 'access' };
    return this.jwtService.sign(payload, { expiresIn: '1h', secret: JWT_SECRET });
  }

  private issueRefreshToken(userId: string, email: string): string {
    const payload: JwtPayload = { sub: userId, email, type: 'refresh' };
    return this.jwtService.sign(payload, { expiresIn: '7d', secret: JWT_SECRET });
  }

  verifyToken(token: string): JwtPayload | null {
    try {
      return this.jwtService.verify<JwtPayload>(token, { secret: JWT_SECRET });
    } catch {
      return null;
    }
  }
}
