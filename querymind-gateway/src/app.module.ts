import { Module } from '@nestjs/common';
import { ThrottlerModule } from '@nestjs/throttler';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AuthModule } from './auth/auth.module';
import { HealthController } from './health/health.controller';
import { RequestLog } from './logging/request-log.entity';
import { QueryModule } from './query/query.module';
import { RabbitMQModule } from './rabbitmq/rabbitmq.module';
import { SessionModule } from './session/session.module';
import { User } from './users/user.entity';

@Module({
  imports: [
    // Rate limiting — 60 req/min per user (key override in guards via user_id)
    ThrottlerModule.forRoot([
      {
        name: 'default',
        ttl: 60000,   // 1 minute window
        limit: 60,
      },
    ]),

    // PostgreSQL for users + request logs
    TypeOrmModule.forRoot({
      type: 'postgres',
      host: process.env.DB_HOST || 'localhost',
      port: parseInt(process.env.DB_PORT || '5432', 10),
      username: process.env.DB_USER || 'admin',
      password: process.env.DB_PASSWORD || 'secret',
      database: process.env.DB_NAME || 'nest-db',
      entities: [User, RequestLog],
      synchronize: true,  // Auto-create tables — disable in production
      logging: process.env.NODE_ENV === 'development',
    }),

    // Global RabbitMQ RPC client (marked @Global in module)
    RabbitMQModule,

    // Feature modules
    AuthModule,
    SessionModule,
    QueryModule,
  ],
  controllers: [HealthController],
})
export class AppModule {}
