import { Controller, Get } from '@nestjs/common';
import { v4 as uuidv4 } from 'uuid';
import { RabbitMQService } from '../rabbitmq/rabbitmq.service';
import { Events } from '../sync/events';

@Controller('health')
export class HealthController {
  constructor(private readonly rabbitmq: RabbitMQService) {}

  @Get()
  async health() {
    const rabbitmqStatus = this.rabbitmq.isConnected() ? 'connected' : 'disconnected';

    // Probe downstream services via RabbitMQ RPC with short timeouts
    const [schemaStatus, execStatus, aiStatus] = await Promise.all([
      this.probeSchema(),
      this.probeExec(),
      this.probeAI(),
    ]);

    return {
      service: 'api-gateway',
      status: 'ok',
      port: parseInt(process.env.PORT || '8000', 10),
      rabbitmq: rabbitmqStatus,
      downstream: {
        schema_service: schemaStatus,
        ai_service: aiStatus,
        execution_service: execStatus,
      },
    };
  }

  private async probeSchema(): Promise<string> {
    try {
      // Send a get_tables request with a dummy session — any reply means the service is alive
      await this.rabbitmq.rpcCall(
        Events.SCHEMA_GET_TABLES_REQUEST,
        {
          correlation_id: uuidv4(),
          session_id: '__health_probe__',
          timestamp: new Date().toISOString(),
        },
        5000,
      );
      return 'ok';
    } catch {
      return 'unreachable';
    }
  }

  private async probeExec(): Promise<string> {
    try {
      await this.rabbitmq.rpcCall(
        Events.EXEC_HISTORY_REQUEST,
        {
          correlation_id: uuidv4(),
          session_id: '__health_probe__',
          timestamp: new Date().toISOString(),
        },
        5000,
      );
      return 'ok';
    } catch {
      return 'unreachable';
    }
  }

  private async probeAI(): Promise<string> {
    // AI service health cannot be easily probed via RabbitMQ without triggering a real generation.
    // We rely on the RabbitMQ connection itself as a proxy for AI service availability.
    // A separate HTTP health endpoint on the AI service can be added if needed.
    return this.rabbitmq.isConnected() ? 'ok' : 'unreachable';
  }
}
