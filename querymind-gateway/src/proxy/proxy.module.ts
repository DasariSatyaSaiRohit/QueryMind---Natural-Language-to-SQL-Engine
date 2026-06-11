import { Module } from '@nestjs/common';
import { QueryMindClient } from './querymind.client';
import { CircuitBreakerService } from './circuit-breaker.service';
import { ProxyController } from './proxy.controller';

@Module({
  controllers: [ProxyController],
  providers: [QueryMindClient, CircuitBreakerService],
  exports: [QueryMindClient],
})
export class ProxyModule {}
