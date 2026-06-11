import { Controller, Get } from '@nestjs/common';
import { ApiTags, ApiOperation } from '@nestjs/swagger';

@ApiTags('health')
@Controller('api/v1')
export class HealthController {
  @Get('health')
  @ApiOperation({ summary: 'Health check' })
  check() {
    return {
      status: 'ok',
      service: 'querymind-gateway',
      timestamp: new Date().toISOString(),
    };
  }
}
