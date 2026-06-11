import 'reflect-metadata';
import { NestFactory, Reflector } from '@nestjs/core';
import { ValidationPipe, ClassSerializerInterceptor } from '@nestjs/common';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { ConfigService } from '@nestjs/config';
import * as helmet from 'helmet';
import { AppModule } from './app.module';
import { GlobalExceptionFilter } from './common/filters/global-exception.filter';
import { ResponseInterceptor } from './common/interceptors/response.interceptor';
import { AppDataSource } from './data-source';

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create(AppModule, {
    bufferLogs: true,
  });

  const configService = app.get(ConfigService);
  const port = configService.get<number>('app.port') ?? 8000;
  const frontendUrl =
    configService.get<string>('app.frontendUrl') || 'http://localhost:3000';

  // ─── Security ────────────────────────────────────────────────────────────────
  app.use((helmet as any)());

  app.enableCors({
    origin: frontendUrl,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'X-Request-Id', 'X-Correlation-Id'],
    credentials: true,
  });

  // ─── Global pipes ─────────────────────────────────────────────────────────
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
      transformOptions: { enableImplicitConversion: true },
      stopAtFirstError: false,
    }),
  );

  // ─── Global filters & interceptors ────────────────────────────────────────
  app.useGlobalFilters(new GlobalExceptionFilter());
  app.useGlobalInterceptors(
    new ClassSerializerInterceptor(app.get(Reflector)),
    new ResponseInterceptor(),
  );

  // ─── Swagger ─────────────────────────────────────────────────────────────
  if (configService.get<string>('app.nodeEnv') !== 'production') {
    const config = new DocumentBuilder()
      .setTitle('QueryMind Gateway')
      .setDescription('API Gateway for QueryMind microservice architecture')
      .setVersion('1.0')
      .addBearerAuth()
      .addServer(`http://localhost:${port}`)
      .build();

    const document = SwaggerModule.createDocument(app, config);
    SwaggerModule.setup('api/docs', app, document);
  }

  // ─── Start server ────────────────────────────────────────────────────────
  await app.listen(port);
  console.log(`QueryMind Gateway running on port ${port}`);

  // ─── Graceful shutdown ───────────────────────────────────────────────────
  const server = app.getHttpServer() as {
    close: (cb: () => void) => void;
  };

  process.on('SIGTERM', async () => {
    console.log('SIGTERM received, shutting down gracefully...');

    server.close(async () => {
      console.log('HTTP server closed');

      try {
        if (AppDataSource.isInitialized) {
          await AppDataSource.destroy();
          console.log('Database connections closed');
        }
      } catch (err) {
        console.error('Error closing database:', err);
      }

      await new Promise<void>((resolve) => setTimeout(resolve, 1000));
      process.exit(0);
    });

    setTimeout(() => {
      console.error('Forced exit after timeout');
      process.exit(1);
    }, 30000);
  });
}

bootstrap().catch((err) => {
  console.error('Failed to start:', err);
  process.exit(1);
});
