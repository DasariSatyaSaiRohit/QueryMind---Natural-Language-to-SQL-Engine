import {
  Injectable,
  CanActivate,
  ExecutionContext,
  HttpException,
  HttpStatus,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Request, Response } from 'express';
import { RedisService } from '../redis/redis.service';
import { JwtPayload } from '../../auth/strategies/jwt.strategy';

@Injectable()
export class RateLimitGuard implements CanActivate {
  private readonly points: number;
  private readonly duration: number;

  constructor(
    private redisService: RedisService,
    private configService: ConfigService,
  ) {
    this.points = this.configService.get<number>('rateLimit.points') ?? 60;
    this.duration = this.configService.get<number>('rateLimit.duration') ?? 60;
  }

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest<Request & { user?: JwtPayload }>();
    const response = context.switchToHttp().getResponse<Response>();

    const identifier = request.user?.user_id || request.ip || 'anonymous';
    const key = `rate_limit:${identifier}`;

    const current = await this.redisService.incr(key);

    if (current === 1) {
      await this.redisService.expire(key, this.duration);
    }

    const ttl = await this.redisService.ttl(key);
    const remaining = Math.max(0, this.points - current);
    const resetAt = Math.floor(Date.now() / 1000) + ttl;

    response.setHeader('X-RateLimit-Limit', this.points);
    response.setHeader('X-RateLimit-Remaining', remaining);
    response.setHeader('X-RateLimit-Reset', resetAt);

    if (current > this.points) {
      throw new HttpException(
        {
          success: false,
          error: {
            code: 'TOO_MANY_REQUESTS',
            message: 'Rate limit exceeded. Please retry after the reset window.',
          },
        },
        HttpStatus.TOO_MANY_REQUESTS,
      );
    }

    return true;
  }
}
