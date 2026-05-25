import {
  CallHandler,
  ExecutionContext,
  Injectable,
  NestInterceptor,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Observable, tap } from 'rxjs';
import { Repository } from 'typeorm';
import { RequestLog } from './request-log.entity';

@Injectable()
export class LoggingInterceptor implements NestInterceptor {
  constructor(
    @InjectRepository(RequestLog)
    private readonly logRepo: Repository<RequestLog>,
  ) {}

  intercept(context: ExecutionContext, next: CallHandler): Observable<any> {
    const req = context.switchToHttp().getRequest();
    const start = Date.now();

    return next.handle().pipe(
      tap({
        next: () => {
          const res = context.switchToHttp().getResponse();
          this.writeLog(req, res.statusCode, Date.now() - start);
        },
        error: (err) => {
          const status = err?.status || 500;
          this.writeLog(req, status, Date.now() - start);
        },
      }),
    );
  }

  private writeLog(req: any, statusCode: number, responseTimeMs: number): void {
    const log = this.logRepo.create({
      user_id: req.user?.user_id || null,
      endpoint: `${req.method} ${req.path}`,
      session_id: req.params?.session_id || req.body?.session_id || null,
      status_code: statusCode,
      response_time_ms: responseTimeMs,
    });
    // Fire-and-forget — never block the response
    this.logRepo.save(log).catch(() => {});
  }
}
