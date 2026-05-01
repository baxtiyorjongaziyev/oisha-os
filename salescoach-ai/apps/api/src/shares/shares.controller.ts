import { Controller, Post, Delete, Get, Param, Body, UseGuards } from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { SharesService } from './shares.service';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { OrgId } from '../common/decorators/org-id.decorator';
import { CreateShareLinkDto } from './dto/create-share-link.dto';

@ApiTags('shares')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('calls/:callId/shares')
export class SharesController {
  constructor(private sharesService: SharesService) {}

  @Post()
  @ApiOperation({ summary: 'Create share link for a call' })
  create(
    @Param('callId') callId: string,
    @OrgId() orgId: string,
    @CurrentUser() user: any,
    @Body() dto: CreateShareLinkDto,
  ) {
    return this.sharesService.create(callId, orgId, user.id, dto);
  }

  @Get()
  @ApiOperation({ summary: 'List share links for a call' })
  list(@Param('callId') callId: string, @OrgId() orgId: string) {
    return this.sharesService.listByCall(callId, orgId);
  }

  @Delete(':linkId')
  @ApiOperation({ summary: 'Revoke share link' })
  revoke(@Param('linkId') linkId: string, @OrgId() orgId: string) {
    return this.sharesService.revoke(linkId, orgId);
  }
}
