import { Injectable, NestMiddleware } from '@nestjs/common';
import { Request, Response, NextFunction } from 'express';
import { v4 as uuid } from 'uuid';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { RequestLog } from '../../entities/request-log.entity';

@Injectable()
export class RequestLoggingMiddleware implements NestMiddleware {
  constructor(
    @InjectRepository(RequestLog)
    private readonly requestLogRepository: Repository<RequestLog>,
  ) {}

  use(req: Request, res: Response, next: NextFunction): void {
    const requestId = uuid();
    const correlationId =
      (req.headers['correlation-id'] as string) || uuid();
    const startTime = Date.now();

    req.headers['x-request-id'] = requestId;
    req.headers['x-correlation-id'] = correlationId;
    res.setHeader('X-Request-Id', requestId);
    res.setHeader('X-Correlation-Id', correlationId);

    res.on('finish', () => {
      const durationMs = Date.now() - startTime;
      const userId = (req as Request & { user?: { user_id: string } }).user
        ?.user_id || 'anonymous';

      // Fire-and-forget log — don't block response
      this.requestLogRepository
        .save({
          request_id: requestId,
          correlation_id: correlationId,
          user_id: userId,
          method: req.method,
          path: req.path,
          status_code: res.statusCode,
          duration_ms: durationMs,
        })
        .catch(() => {
          // Silently ignore log failures
        });
    });

    next();
  }
}
