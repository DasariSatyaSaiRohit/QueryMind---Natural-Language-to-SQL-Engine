import { Module } from '@nestjs/common';
import { AuthModule } from '../auth/auth.module';
import { QueryController } from './query.controller';
import { QueryService } from './query.service';
import { QueryWsGateway } from './query-ws.gateway';

@Module({
  imports: [AuthModule],
  providers: [QueryService, QueryWsGateway],
  controllers: [QueryController],
  exports: [QueryWsGateway],
})
export class QueryModule {}
