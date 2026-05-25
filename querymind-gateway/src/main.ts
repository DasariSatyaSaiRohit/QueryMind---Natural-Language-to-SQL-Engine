import { ValidationPipe } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { GlobalExceptionFilter } from './common/filters/global-exception.filter';
import { QueryWsGateway } from './query/query-ws.gateway';

async function bootstrap() {
  console.log("********",process.env.DB_USER || 'admin',);
  const app = await NestFactory.create(AppModule);

  // CORS — allow React frontend and internal tooling
  app.enableCors({
    origin: [
      'http://localhost:3000',
      'http://127.0.0.1:3000',
      process.env.FRONTEND_URL || 'http://localhost:3000',
    ],
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization'],
    credentials: true,
  });

  // Global DTO validation
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: false,
      transform: true,
      transformOptions: { enableImplicitConversion: true },
    }),
  );
  
  // Global exception filter — never expose stack traces to clients
  app.useGlobalFilters(new GlobalExceptionFilter());

  const port = parseInt(process.env.PORT || '8000', 10);

  // Start listening — get the underlying HTTP server so we can attach the WS proxy
  const server = await app.listen(port);

  // Attach the WebSocket proxy to the same HTTP server.
  // This is separate from @nestjs/websockets because we need a transparent
  // bidirectional proxy, not a NestJS WebSocket event handler.
  const queryWsGateway = app.get(QueryWsGateway);
  queryWsGateway.attach(server);

  console.log(`
╔══════════════════════════════════════════════════╗
║          QueryMind API Gateway                   ║
║                                                  ║
║  HTTP  :  http://localhost:${port}                 ║
║  WS    :  ws://localhost:${port}/ws/query/:id      ║
║  RabbitMQ: ${process.env.AMQP_URL || 'amqp://localhost:5672'}  ║
╚══════════════════════════════════════════════════╝
  `);
}

bootstrap().catch((err) => {
  console.error('Failed to start QueryMind Gateway:', err);
  process.exit(1);
});
