import {
  Injectable,
  Logger,
  UnprocessableEntityException,
} from '@nestjs/common';
import { v4 as uuidv4 } from 'uuid';
import { RabbitMQService } from '../rabbitmq/rabbitmq.service';
import { Events } from '../sync/events';
import { AskQueryDto } from './dto/ask-query.dto';
import { ExecuteOnlyDto } from './dto/execute-only.dto';

@Injectable()
export class QueryService {
  private readonly logger = new Logger(QueryService.name);

  constructor(private readonly rabbitmq: RabbitMQService) {}

  async ask(dto: AskQueryDto): Promise<any> {
    const timestamp = new Date().toISOString();

    // Step 1 — AI generation via RabbitMQ RPC
    this.logger.log(`AI generate request for session ${dto.session_id}`);
    const aiReply = await this.rabbitmq.rpcCall(
      Events.AI_QUERY_GENERATE_REQUEST,
      {
        correlation_id: uuidv4(),
        session_id: dto.session_id,
        timestamp,
        question: dto.question,
      },
      60000,  // 60s timeout — AI generation can be slow
    );

    if (!aiReply.success) {
      throw new UnprocessableEntityException({
        error: aiReply.error_type || 'ai_error',
        message: aiReply.error || 'AI query generation failed',
        invalid_references: aiReply.invalid_references || [],
      });
    }

    // Step 2 — SQL execution via RabbitMQ RPC (depends on AI result)
    this.logger.log(`Exec run request for session ${dto.session_id}`);
    const execReply = await this.rabbitmq.rpcCall(
      Events.EXEC_RUN_REQUEST,
      {
        correlation_id: uuidv4(),
        session_id: dto.session_id,
        timestamp: new Date().toISOString(),
        sql: aiReply.sql,
        page: 1,
        page_size: 50,
      },
      30000,
    );

    if (!execReply.success) {
      throw new UnprocessableEntityException({
        error: execReply.error_type || 'execution_failed',
        message: execReply.error || 'Query execution failed',
        sql: aiReply.sql,
      });
    }

    // Combine AI + execution result into a single response
    return {
      session_id: dto.session_id,
      question: dto.question,
      rag_context: aiReply.rag_context || null,
      sql: aiReply.sql,
      rationale: aiReply.rationale,
      explanation: aiReply.explanation,
      tables_used: aiReply.tables_used || [],
      validation: aiReply.validation || null,
      generation_time_ms: aiReply.generation_time_ms,
      cache_hit: aiReply.cache_hit || false,
      results: {
        columns: execReply.columns || [],
        rows: execReply.rows || [],
        pagination: execReply.pagination || null,
        execution_time_ms: execReply.execution_time_ms,
        truncated: execReply.truncated || false,
        truncation_warning: execReply.truncation_warning || null,
      },
    };
  }

  async executeOnly(dto: ExecuteOnlyDto): Promise<any> {
    const execReply = await this.rabbitmq.rpcCall(
      Events.EXEC_RUN_REQUEST,
      {
        correlation_id: uuidv4(),
        session_id: dto.session_id,
        timestamp: new Date().toISOString(),
        sql: dto.sql,
        page: dto.page || 1,
        page_size: dto.page_size || 50,
      },
      30000,
    );

    if (!execReply.success) {
      throw new UnprocessableEntityException({
        error: execReply.error_type || 'execution_failed',
        message: execReply.error || 'Query execution failed',
        sql: dto.sql,
      });
    }

    return execReply;
  }

  async getHistory(sessionId: string): Promise<any> {
    const reply = await this.rabbitmq.rpcCall(
      Events.EXEC_HISTORY_REQUEST,
      {
        correlation_id: uuidv4(),
        session_id: sessionId,
        timestamp: new Date().toISOString(),
      },
      10000,
    );

    if (!reply.success) {
      return { session_id: sessionId, history: [] };
    }

    return { session_id: sessionId, history: reply.history || [] };
  }
}
