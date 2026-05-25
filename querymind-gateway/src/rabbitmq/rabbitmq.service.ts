import {
  Injectable,
  Logger,
  OnModuleDestroy,
  OnModuleInit,
} from '@nestjs/common';
import * as amqp from 'amqplib';
import { v4 as uuidv4 } from 'uuid';
import { EXCHANGE } from '../sync/events';

@Injectable()
export class RabbitMQService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(RabbitMQService.name);
  // amqplib v0.10+: amqp.connect() returns ChannelModel, not Connection
  private connection: amqp.ChannelModel;
  private channel: amqp.Channel;
  private pendingReplies = new Map<string, (reply: any) => void>();
  private connected = false;

  async onModuleInit(): Promise<void> {
    await this.connect();
  }

  private async connect(): Promise<void> {
    const amqpUrl =
      process.env.AMQP_URL || 'amqp://querymind:querymind_pass@localhost:5672/';
    try {
      this.connection = await amqp.connect(amqpUrl);
      this.channel = await this.connection.createChannel();

      await this.channel.assertExchange(EXCHANGE, 'topic', { durable: true });

      // Direct reply-to consumer — replies arrive here matched by correlationId
      await this.channel.consume(
        'amq.rabbitmq.reply-to',
        (msg) => {
          if (!msg) return;
          const correlationId = msg.properties.correlationId;
          const resolve = this.pendingReplies.get(correlationId);
          if (resolve) {
            this.pendingReplies.delete(correlationId);
            try {
              resolve(JSON.parse(msg.content.toString()));
            } catch (err) {
              this.logger.error(
                `Failed to parse reply for correlationId ${correlationId}: ${err.message}`,
              );
            }
          } else {
            this.logger.warn(`No pending handler for correlationId: ${correlationId}`);
          }
        },
        { noAck: true },
      );

      this.connected = true;
      this.logger.log('Connected to RabbitMQ — listening on amq.rabbitmq.reply-to');

      // amqplib v0.10+ wraps the raw socket in .connection (typed as any to avoid
      // fighting the internal Connection type that doesn't expose these events publicly)
      const rawConn = (this.connection as any).connection;
      if (rawConn) {
        rawConn.on('close', () => {
          this.connected = false;
          this.logger.warn('RabbitMQ TCP connection closed — reconnecting in 5s...');
          setTimeout(() => this.connect(), 5000);
        });
        rawConn.on('error', (err: Error) => {
          this.logger.error(`RabbitMQ TCP error: ${err.message}`);
        });
      }
    } catch (err) {
      this.connected = false;
      this.logger.error(
        `Failed to connect to RabbitMQ: ${err.message}. Retrying in 5s...`,
      );
      setTimeout(() => this.connect(), 5000);
    }
  }

  /**
   * Publish a message and await a reply via amq.rabbitmq.reply-to (Direct Reply-to).
   * Blocks until the matching correlationId reply arrives or timeout is exceeded.
   */
  async rpcCall(
    routingKey: string,
    payload: object,
    timeoutMs = 30000,
  ): Promise<any> {
    if (!this.connected || !this.channel) {
      throw new Error('RabbitMQ not connected — cannot perform RPC call');
    }

    const correlationId = uuidv4();

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingReplies.delete(correlationId);
        reject(
          new Error(`RPC timeout after ${timeoutMs}ms for routing key: ${routingKey}`),
        );
      }, timeoutMs);

      this.pendingReplies.set(correlationId, (reply) => {
        clearTimeout(timer);
        resolve(reply);
      });

      try {
        const published = this.channel.publish(
          EXCHANGE,
          routingKey,
          Buffer.from(JSON.stringify(payload)),
          {
            correlationId,
            replyTo: 'amq.rabbitmq.reply-to',
            contentType: 'application/json',
            persistent: true,
          },
        );

        if (!published) {
          clearTimeout(timer);
          this.pendingReplies.delete(correlationId);
          reject(
            new Error(`Failed to publish to ${routingKey} — channel buffer full`),
          );
        }
      } catch (err) {
        clearTimeout(timer);
        this.pendingReplies.delete(correlationId);
        reject(err);
      }
    });
  }

  /** Fire-and-forget publish — no reply expected. */
  publish(routingKey: string, payload: object): void {
    if (!this.connected || !this.channel) {
      this.logger.error('RabbitMQ not connected — dropping fire-and-forget message');
      return;
    }
    this.channel.publish(
      EXCHANGE,
      routingKey,
      Buffer.from(JSON.stringify(payload)),
      { contentType: 'application/json', persistent: true },
    );
  }

  isConnected(): boolean {
    return this.connected;
  }

  async onModuleDestroy(): Promise<void> {
    try {
      if (this.channel) await this.channel.close();
      // End the underlying TCP socket — cast to any to bypass amqplib internal typings
      const rawConn = (this.connection as any)?.connection;
      if (rawConn?.end) rawConn.end();
      this.logger.log('RabbitMQ connection closed cleanly');
    } catch (err) {
      this.logger.error(`Error closing RabbitMQ: ${err.message}`);
    }
  }
}