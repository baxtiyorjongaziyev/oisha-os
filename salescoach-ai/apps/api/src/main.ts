import { NestFactory } from '@nestjs/core';
import { ValidationPipe, VersioningType } from '@nestjs/common';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { IoAdapter } from '@nestjs/platform-socket.io';
import { AppModule } from './app.module';

async function bootstrap() {
  // Use default Express adapter (Socket.io incompatible with Fastify)
  const app = await NestFactory.create(AppModule);

  app.enableCors({
    origin: process.env.CORS_ORIGIN?.split(',') ?? ['http://localhost:3000'],
    credentials: true,
  });

  // WebSocket adapter
  app.useWebSocketAdapter(new IoAdapter(app));

  app.enableVersioning({ type: VersioningType.URI, defaultVersion: '1' });

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  const config = new DocumentBuilder()
    .setTitle('SalesCoach AI API')
    .setDescription(
      'AI-powered sales call analysis + autonomous negotiation platform.\n\n' +
      '**WebSocket:** `ws://<host>/coaching` — real-time call coaching\n' +
      '**Events in:** `call:join`, `call:transcript`, `call:end`\n' +
      '**Events out:** `coaching:tip`, `coaching:alert`, `coaching:scorecard`, `call:status`',
    )
    .setVersion('1.0')
    .addBearerAuth()
    .build();

  SwaggerModule.setup('docs', app, SwaggerModule.createDocument(app, config));

  const port = process.env.PORT ?? 4000;
  await app.listen(port, '0.0.0.0');
  console.log(`🚀 SalesCoach AI API running on port ${port}`);
  console.log(`📖 Swagger: http://localhost:${port}/docs`);
  console.log(`🔌 WebSocket: ws://localhost:${port}/coaching`);
}

bootstrap();
