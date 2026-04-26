import { Controller, Get, Post, Param, Body, UseGuards, Query } from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { CallsService } from './calls.service';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { OrgId } from '../common/decorators/org-id.decorator';
import { CreateCallDto } from './dto/create-call.dto';

@ApiTags('calls')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('calls')
export class CallsController {
  constructor(private callsService: CallsService) {}

  @Post()
  @ApiOperation({ summary: 'Initiate audio upload — returns presigned S3 URL' })
  initiateUpload(
    @OrgId() orgId: string,
    @CurrentUser() user: any,
    @Body() dto: CreateCallDto,
  ) {
    return this.callsService.initiateUpload(orgId, user.id, dto);
  }

  @Post(':id/confirm')
  @ApiOperation({ summary: 'Confirm upload done — enqueues transcription job' })
  confirmUpload(@Param('id') id: string, @OrgId() orgId: string) {
    return this.callsService.confirmUpload(id, orgId);
  }

  @Get()
  @ApiOperation({ summary: 'List org calls' })
  findAll(@OrgId() orgId: string, @Query('managerId') managerId?: string) {
    return this.callsService.findAll(orgId, managerId);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get call detail with presigned audio URL' })
  findOne(@Param('id') id: string, @OrgId() orgId: string) {
    return this.callsService.findOne(id, orgId);
  }

  @Get(':id/transcript')
  @ApiOperation({ summary: 'Get call transcript segments' })
  getTranscript(@Param('id') id: string, @OrgId() orgId: string) {
    return this.callsService.getTranscript(id, orgId);
  }
}
