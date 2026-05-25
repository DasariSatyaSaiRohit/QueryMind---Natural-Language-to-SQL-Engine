import {
  BadRequestException,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { v4 as uuidv4 } from 'uuid';
import { RabbitMQService } from '../rabbitmq/rabbitmq.service';
import { Events } from '../sync/events';

@Injectable()
export class SessionService {
  private readonly logger = new Logger(SessionService.name);

  constructor(private readonly rabbitmq: RabbitMQService) {}

  async connect(connectionString: string): Promise<any> {
    const sessionId = uuidv4();
    const timestamp = new Date().toISOString();

    this.logger.log(`Initiating session connect: ${sessionId}`);

    // Fan-out to Schema Service and Execution Service in parallel
    const [schemaReply, execReply] = await Promise.all([
      this.rabbitmq.rpcCall(
        Events.SCHEMA_CONNECT_REQUEST,
        {
          correlation_id: uuidv4(),
          session_id: sessionId,
          timestamp,
          connection_string: connectionString,
        },
        30000,
      ).catch((err) => ({ success: false, error: err.message })),

      this.rabbitmq.rpcCall(
        Events.EXEC_INIT_REQUEST,
        {
          correlation_id: uuidv4(),
          session_id: sessionId,
          timestamp,
          connection_string: connectionString,
        },
        30000,
      ).catch((err) => ({ success: false, error: err.message })),
    ]);

    if (!schemaReply.success) {
      throw new BadRequestException({
        error: 'connection_failed',
        message: schemaReply.message || schemaReply.error || 'Schema Service failed to connect',
      });
    }

    if (!execReply.success) {
      throw new BadRequestException({
        error: 'connection_failed',
        message: execReply.error || 'Execution Service failed to initialize session',
      });
    }

    return {
      session_id: sessionId,
      database_name: schemaReply.database_name,
      status: 'connected',
      connected_at: schemaReply.connected_at || timestamp,
    };
  }

  async getSchema(sessionId: string, relevantTables?: string[]): Promise<any> {
    const reply = await this.rabbitmq.rpcCall(
      Events.SCHEMA_GET_REQUEST,
      {
        correlation_id: uuidv4(),
        session_id: sessionId,
        timestamp: new Date().toISOString(),
        relevant_tables: relevantTables || [],
      },
      20000,
    );

    if (!reply.success) {
      throw new NotFoundException({
        error: 'session_not_found',
        message: reply.error || 'No active session for the given session_id',
      });
    }

    return reply.schema;
  }

  async disconnect(sessionId: string): Promise<any> {
    const reply = await this.rabbitmq.rpcCall(
      Events.SCHEMA_DISCONNECT_REQUEST,
      {
        correlation_id: uuidv4(),
        session_id: sessionId,
        timestamp: new Date().toISOString(),
      },
      10000,
    );

    if (!reply.success) {
      throw new BadRequestException({
        error: 'disconnect_failed',
        message: reply.error || 'Failed to disconnect session',
      });
    }

    return { session_id: sessionId, status: 'disconnected' };
  }
}
