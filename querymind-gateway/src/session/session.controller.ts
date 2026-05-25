import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  Post,
  Query,
  Request,
  UseGuards,
} from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { SessionService } from './session.service';

@Controller('session')
@UseGuards(JwtAuthGuard)
export class SessionController {
  constructor(private readonly sessionService: SessionService) {}

  @Post('connect')
  async connect(@Body() body: { connection_string: string }) {
    return this.sessionService.connect(body.connection_string);
  }

  @Get(':session_id/schema')
  async getSchema(
    @Param('session_id') sessionId: string,
    @Query('relevant_tables') relevantTables?: string,
  ) {
    const tables = relevantTables ? relevantTables.split(',').map((t) => t.trim()) : [];
    return this.sessionService.getSchema(sessionId, tables);
  }

  @Delete(':session_id/disconnect')
  async disconnect(@Param('session_id') sessionId: string) {
    return this.sessionService.disconnect(sessionId);
  }
}
