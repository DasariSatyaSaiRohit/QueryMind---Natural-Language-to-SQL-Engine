import {
  Controller,
  Post,
  Get,
  Delete,
  Body,
  Param,
  Request,
  UseGuards,
  Query,
} from '@nestjs/common';
import {
  ApiTags,
  ApiBearerAuth,
  ApiOperation,
  ApiResponse,
} from '@nestjs/swagger';
import { v4 as uuid } from 'uuid';
import { QueryMindClient } from '../proxy/querymind.client';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';
import { ForwardRequestDto } from '../auth/dto/auth.dto';
import { JwtPayload } from '../auth/strategies/jwt.strategy';

interface AuthenticatedRequest {
  user: JwtPayload;
  headers: Record<string, string>;
}

function correlationHeaders(req: AuthenticatedRequest): Record<string, string> {
  return {
    'correlation-id':
      req.headers['x-correlation-id'] || uuid(),
    'x-user-id': req.user.user_id,
  };
}

@ApiTags('proxy')
@Controller('api/v1')
@UseGuards(JwtAuthGuard)
@ApiBearerAuth()
export class ProxyController {
  constructor(private readonly queryMindClient: QueryMindClient) {}

  // ─── Connections ────────────────────────────────────────────────────────────

  @Post('connections/add')
  @ApiOperation({ summary: 'Add a database connection' })
  @ApiResponse({ status: 201, description: 'Connection added' })
  async addConnection(
    @Body() body: ForwardRequestDto,
    @Request() req: AuthenticatedRequest,
  ) {
    return this.queryMindClient.post('/connections/add', {
      ...body,
      user_id: req.user.user_id,
    }, { headers: correlationHeaders(req) });
  }

  @Get('connections/list')
  @ApiOperation({ summary: 'List database connections' })
  async listConnections(@Request() req: AuthenticatedRequest) {
    return this.queryMindClient.get(
      '/connections/list',
      { user_id: req.user.user_id },
      correlationHeaders(req),
    );
  }

  @Post('connections/test_connection')
  @ApiOperation({ summary: 'Test a database connection' })
  async testConnection(
    @Body() body: ForwardRequestDto,
    @Request() req: AuthenticatedRequest,
  ) {
    
    return this.queryMindClient.post('/connections/test_connection', {
      ...body,
      user_id: req.user.user_id,
    }, { headers: correlationHeaders(req) });
  }

  @Delete('connections/:id')
  @ApiOperation({ summary: 'Delete a database connection' })
  async deleteConnection(
    @Param('id') id: string,
    @Request() req: AuthenticatedRequest,
  ) {
    return this.queryMindClient.delete(
      `/connections/${id}`,
      { user_id: req.user.user_id },
      { headers: correlationHeaders(req) },
    );
  }

  // ─── Sessions ───────────────────────────────────────────────────────────────

  @Post('session/connect')
  @ApiOperation({ summary: 'Start a new query session' })
  async connectSession(
    @Body() body: ForwardRequestDto,
    @Request() req: AuthenticatedRequest,
  ) {
    return this.queryMindClient.post('/session/connect', {
      ...body,
      user_id: req.user.user_id,
    }, { headers: correlationHeaders(req) });
  }

  @Get('session/:sessionId/schema')
  @ApiOperation({ summary: 'Get schema for a session' })
  async getSchema(
    @Param('sessionId') sessionId: string,
    @Request() req: AuthenticatedRequest,
  ) {
    return this.queryMindClient.get(
      `/session/${sessionId}/schema`,
      {},
      correlationHeaders(req),
    );
  }

  // ─── Queries ─────────────────────────────────────────────────────────────────

  @Post('query/ask')
  @ApiOperation({ summary: 'Ask a natural language question (non-blocking)' })
  async askQuery(
    @Body() body: ForwardRequestDto,
    @Request() req: AuthenticatedRequest,
  ) {
    return this.queryMindClient.post('/query/ask', {
      ...body,
      user_id: req.user.user_id,
    }, { headers: correlationHeaders(req) });
  }

  @Post('query/execute')
  @ApiOperation({ summary: 'Execute a generated SQL query' })
  async executeQuery(
    @Body() body: ForwardRequestDto,
    @Request() req: AuthenticatedRequest,
  ) {
    return this.queryMindClient.post('/query/execute', {
      ...body,
      user_id: req.user.user_id,
    }, { headers: correlationHeaders(req) });
  }

  @Get('query/history/:sessionId')
  @ApiOperation({ summary: 'Get query history for a session' })
  async getHistory(
    @Param('sessionId') sessionId: string,
    @Query('page') page: number = 1,
    @Query('page_size') pageSize: number = 50,
    @Request() req: AuthenticatedRequest,
  ) {
    return this.queryMindClient.get(
      `/query/history/${sessionId}`,
      { page, page_size: pageSize },
      correlationHeaders(req),
    );
  }
}
