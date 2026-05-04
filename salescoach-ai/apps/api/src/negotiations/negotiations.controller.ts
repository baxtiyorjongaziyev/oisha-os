import { Controller, Post, Get, Body, Param, Query, UseGuards } from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { OrgId } from '../common/decorators/org-id.decorator';
import { NegotiationsService } from './negotiations.service';
import { NegotiateDto, RealtimeSuggestionDto } from './dto/negotiate.dto';

@ApiTags('negotiations')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('negotiations')
export class NegotiationsController {
  constructor(private service: NegotiationsService) {}

  @Post('suggest')
  @ApiOperation({
    summary: 'Get AI-powered negotiation suggestion for a customer message',
    description: 'Returns suggested reply, assessment, talking points, and surgical mission.',
  })
  suggest(
    @OrgId() orgId: string,
    @CurrentUser() user: any,
    @Body() dto: NegotiateDto,
  ) {
    return this.service.getSuggestion(orgId, user.id, dto);
  }

  @Post('realtime')
  @ApiOperation({
    summary: 'Real-time in-call coaching tip (low latency)',
    description: 'Use during live calls. Returns a single actionable tip in <1s.',
  })
  realtimeTip(
    @OrgId() orgId: string,
    @CurrentUser() user: any,
    @Body() dto: RealtimeSuggestionDto,
  ) {
    return this.service.getRealtimeSuggestion(orgId, user.id, dto);
  }

  @Post('objection/:type')
  @ApiOperation({
    summary: 'Get objection handling response',
    description: 'Types: price, trust, timing, competition, legal, budget, authority',
  })
  handleObjection(
    @Param('type') type: string,
    @Body() body: { context: string; language?: 'uz' | 'ru' | 'en' },
  ) {
    return this.service.handleObjection(type, body.context, body.language ?? 'uz');
  }

  @Get('pipeline-insights')
  @ApiOperation({ summary: 'Pipeline insights from scored calls (last N days)' })
  pipelineInsights(
    @OrgId() orgId: string,
    @Query('days') days?: string,
  ) {
    return this.service.getPipelineInsights(orgId, days ? +days : 7);
  }
}
