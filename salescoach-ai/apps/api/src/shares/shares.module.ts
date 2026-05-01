import { Module } from '@nestjs/common';
import { SharesController } from './shares.controller';
import { SharesService } from './shares.service';
import { PublicShareController } from './public-share.controller';

@Module({
  controllers: [SharesController, PublicShareController],
  providers: [SharesService],
})
export class SharesModule {}
