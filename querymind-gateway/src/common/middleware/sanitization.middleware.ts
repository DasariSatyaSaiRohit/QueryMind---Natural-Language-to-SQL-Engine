import { Injectable, NestMiddleware } from '@nestjs/common';
import { Request, Response, NextFunction } from 'express';

@Injectable()
export class SanitizationMiddleware implements NestMiddleware {
  use(req: Request, _res: Response, next: NextFunction): void {
    const sanitize = (obj: unknown): unknown => {
      if (typeof obj === 'string') {
        let sanitized = obj.trim();
        // Remove null bytes
        sanitized = sanitized.replace(/\0/g, '');
        // Remove dangerous control characters (preserve newline \n=0x0A and tab \t=0x09)
        sanitized = sanitized.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');
        return sanitized;
      }

      if (Array.isArray(obj)) {
        return obj.map(sanitize);
      }

      if (typeof obj === 'object' && obj !== null) {
        const sanitized: Record<string, unknown> = {};
        for (const key in obj as Record<string, unknown>) {
          if (Object.prototype.hasOwnProperty.call(obj, key)) {
            sanitized[key.trim()] = sanitize(
              (obj as Record<string, unknown>)[key],
            );
          }
        }
        return sanitized;
      }

      return obj;
    };

    if (req.body && Object.keys(req.body as object).length > 0) {
      req.body = sanitize(req.body) as Record<string, unknown>;
    }
    if (req.query && Object.keys(req.query).length > 0) {
      req.query = sanitize(req.query) as Record<
        string,
        string | string[] | undefined
      >;
    }
    if (req.params && Object.keys(req.params).length > 0) {
      req.params = sanitize(req.params) as Record<string, string>;
    }

    next();
  }
}
