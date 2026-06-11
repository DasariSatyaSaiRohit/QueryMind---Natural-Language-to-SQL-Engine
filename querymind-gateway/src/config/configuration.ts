import { registerAs } from '@nestjs/config';

export const appConfig = registerAs('app', () => ({
  nodeEnv: process.env.NODE_ENV || 'development',
  port: parseInt(process.env.PORT || '8000', 10),
  frontendUrl: process.env.FRONTEND_URL || 'http://localhost:3000',
  logLevel: process.env.LOG_LEVEL || 'info',
}));

export const jwtConfig = registerAs('jwt', () => ({
  secret: process.env.JWT_SECRET || 'changeme-32-char-secret-key-here',
  accessExpiry: parseInt(process.env.JWT_ACCESS_EXPIRY || '3600', 10),
  refreshExpiry: parseInt(process.env.JWT_REFRESH_EXPIRY || '604800', 10),
}));

export const databaseConfig = registerAs('database', () => ({
  url: process.env.DATABASE_URL,
  synchronize: process.env.TYPEORM_SYNCHRONIZE === 'true',
}));

export const redisConfig = registerAs('redis', () => ({
  host: process.env.REDIS_HOST || 'localhost',
  port: parseInt(process.env.REDIS_PORT || '6379', 10),
}));

export const proxyConfig = registerAs('proxy', () => ({
  queryMindServiceUrl:
    process.env.QUERYMIND_SERVICE_URL ||
    'http://querymind-service:8001/api/v1',
  maxRetries: parseInt(process.env.MAX_RETRIES || '3', 10),
  retryDelayBase: parseInt(process.env.RETRY_DELAY_BASE || '1000', 10),
  circuitBreakerThreshold: parseInt(
    process.env.CIRCUIT_BREAKER_THRESHOLD || '5',
    10,
  ),
  circuitBreakerResetTimeout: parseInt(
    process.env.CIRCUIT_BREAKER_RESET_TIMEOUT || '60000',
    10,
  ),
  requestTimeout: 30000,
}));

export const rateLimitConfig = registerAs('rateLimit', () => ({
  points: parseInt(process.env.RATE_LIMIT_POINTS || '60', 10),
  duration: parseInt(process.env.RATE_LIMIT_DURATION || '60', 10),
}));
