import {
  Body,
  Controller,
  Get,
  Param,
  Post,
  UseGuards,
} from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { AskQueryDto } from './dto/ask-query.dto';
import { ExecuteOnlyDto } from './dto/execute-only.dto';
import { QueryService } from './query.service';

@Controller('query')
@UseGuards(JwtAuthGuard)
export class QueryController {
  constructor(private readonly queryService: QueryService) {}

  @Post('ask')
  async ask(@Body() dto: AskQueryDto) {
    return this.queryService.ask(dto);
  }

  @Post('execute-only')
  async executeOnly(@Body() dto: ExecuteOnlyDto) {
    return this.queryService.executeOnly(dto);
  }

  @Get('history/:session_id')
  async getHistory(@Param('session_id') sessionId: string) {
    return this.queryService.getHistory(sessionId);
  }
}
