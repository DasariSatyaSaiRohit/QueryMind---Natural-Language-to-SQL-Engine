import {
  Module,
  MiddlewareConsumer,
  NestModule,
  RequestMethod,
} from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import {
  appConfig,
  jwtConfig,
  databaseConfig,
  redisConfig,
  proxyConfig,
  rateLimitConfig,
} from './config/configuration';
import { AuthModule } from './auth/auth.module';
import { ProxyModule } from './proxy/proxy.module';
import { RedisModule } from './common/redis/redis.module';
import { HealthController } from './common/health.controller';
import { User } from './entities/user.entity';
import { RequestLog } from './entities/request-log.entity';
import { SanitizationMiddleware } from './common/middleware/sanitization.middleware';
import { RequestLoggingMiddleware } from './common/middleware/request-logging.middleware';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      load: [
        appConfig,
        jwtConfig,
        databaseConfig,
        redisConfig,
        proxyConfig,
        rateLimitConfig,
      ],
    }),

    TypeOrmModule.forRootAsync({
      useFactory: () => ({
        type: 'postgres' as const,
        url: process.env.DATABASE_URL,
        entities: [User, RequestLog],
        migrations: [__dirname + '/migrations/*.ts'],
        synchronize: process.env.NODE_ENV === 'development',
        logging: process.env.NODE_ENV === 'development',
        migrationsRun: process.env.NODE_ENV !== 'development',
      }),
    }),

    TypeOrmModule.forFeature([RequestLog]),

    RedisModule,
    AuthModule,
    ProxyModule,
  ],
  controllers: [HealthController],
})
export class AppModule implements NestModule {
  configure(consumer: MiddlewareConsumer): void {
    consumer
      .apply(SanitizationMiddleware)
      .forRoutes({ path: '*', method: RequestMethod.ALL });

    consumer
      .apply(RequestLoggingMiddleware)
      .forRoutes({ path: '*', method: RequestMethod.ALL });
  }
}
