import { Controller, Get, Param, Query, UseGuards } from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { ScorecardsService } from './scorecards.service';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';
import { OrgId } from '../common/decorators/org-id.decorator';

@ApiTags('scorecards')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('scorecards')
export class ScorecardsController {
  constructor(private scorecardsService: ScorecardsService) {}

  @Get()
  @ApiOperation({ summary: 'List scorecards for org' })
  listByOrg(
    @OrgId() orgId: string,
    @Query('limit') limit?: number,
    @Query('offset') offset?: number,
  ) {
    return this.scorecardsService.listByOrg(orgId, limit, offset);
  }

  @Get('call/:callId')
  @ApiOperation({ summary: 'Get scorecard for a specific call' })
  findByCall(@Param('callId') callId: string, @OrgId() orgId: string) {
    return this.scorecardsService.findByCall(callId, orgId);
  }
}
