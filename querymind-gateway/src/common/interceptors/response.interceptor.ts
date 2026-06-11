import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
} from '@nestjs/common';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { Request } from 'express';

export interface StandardResponse<T> {
  success: true;
  data: T;
  timestamp: string;
  correlation_id: string;
  request_id: string;
}

@Injectable()
export class ResponseInterceptor<T>
  implements NestInterceptor<T, StandardResponse<T> | T>
{
  intercept(
    context: ExecutionContext,
    next: CallHandler<T>,
  ): Observable<StandardResponse<T> | T> {
    const request = context.switchToHttp().getRequest<Request>();
    const requestId =
      (request.headers['x-request-id'] as string) || 'unknown';
    const correlationId =
      (request.headers['x-correlation-id'] as string) || 'unknown';

    return next.handle().pipe(
      map((data) => {
        // If already wrapped (e.g. from proxy passthrough), return as-is
        if (
          data &&
          typeof data === 'object' &&
          'success' in (data as object)
        ) {
          return data;
        }

        return {
          success: true as const,
          data,
          timestamp: new Date().toISOString(),
          correlation_id: correlationId,
          request_id: requestId,
        };
      }),
    );
  }
}
