import { Controller, Get, UseGuards } from '@nestjs/common';
import { ApiBearerAuth, ApiTags } from '@nestjs/swagger';
import { OrganizationsService } from './organizations.service';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';
import { OrgId } from '../common/decorators/org-id.decorator';

@ApiTags('organizations')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('organizations')
export class OrganizationsController {
  constructor(private orgsService: OrganizationsService) {}

  @Get('me')
  getMyOrg(@OrgId() orgId: string) {
    return this.orgsService.findById(orgId);
  }

  @Get('me/usage')
  getUsage(@OrgId() orgId: string) {
    return this.orgsService.getUsage(orgId);
  }
}
