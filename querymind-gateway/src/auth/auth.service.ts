import { Injectable, UnauthorizedException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import * as bcrypt from 'bcrypt';
import { UsersService } from '../users/users.service';
import {
  RegisterRequestDto,
  LoginRequestDto,
} from './dto/auth.dto';
import { User } from '../entities/user.entity';
import { JwtPayload } from './strategies/jwt.strategy';

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

@Injectable()
export class AuthService {
  constructor(
    private usersService: UsersService,
    private jwtService: JwtService,
    private configService: ConfigService,
  ) {}

  async register(dto: RegisterRequestDto): Promise<{ tokens: TokenPair; user: User }> {
    const user = await this.usersService.createUser(dto);
    const tokens = this.generateTokens(user);
    return { tokens, user };
  }

  async login(dto: LoginRequestDto): Promise<{ tokens: TokenPair; user: User }> {
    const user = await this.usersService.findByEmail(dto.email);

    if (!user || !(await bcrypt.compare(dto.password, user.password_hash))) {
      throw new UnauthorizedException('Invalid credentials');
    }

    const tokens = this.generateTokens(user);
    return { tokens:tokens,user };
  }

  async refresh(refreshToken: string): Promise<TokenPair> {
    let payload: JwtPayload;

    try {
      payload = this.jwtService.verify<JwtPayload>(refreshToken, {
        secret: this.configService.get<string>('jwt.secret'),
      });
    } catch {
      throw new UnauthorizedException('Invalid or expired refresh token');
    }

    if (payload.type !== 'refresh') {
      throw new UnauthorizedException('Invalid token type');
    }

    const user = await this.usersService.findById(payload.user_id);
    if (!user) {
      throw new UnauthorizedException('User not found');
    }

    return this.generateTokens(user);
  }

  private generateTokens(user: User): TokenPair {
    const accessPayload: JwtPayload = {
      user_id: user.user_id,
      email: user.email,
      type: 'access',
    };

    const refreshPayload: JwtPayload = {
      user_id: user.user_id,
      email: user.email,
      type: 'refresh',
    };

    const accessExpiry =
      this.configService.get<number>('jwt.accessExpiry') ?? 3600;
    const refreshExpiry =
      this.configService.get<number>('jwt.refreshExpiry') ?? 604800;

    return {
      access_token: this.jwtService.sign(accessPayload, {
        expiresIn: accessExpiry,
      }),
      refresh_token: this.jwtService.sign(refreshPayload, {
        expiresIn: refreshExpiry,
      }),
    };
  }
}
