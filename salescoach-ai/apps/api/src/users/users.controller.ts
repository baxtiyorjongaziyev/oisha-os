import { Controller, Get, Patch, Delete, Body, Param, UseGuards } from '@nestjs/common';
import { ApiBearerAuth, ApiTags } from '@nestjs/swagger';
import { UsersService } from './users.service';
import { JwtAuthGuard } from '../common/guards/jwt-auth.guard';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { OrgId } from '../common/decorators/org-id.decorator';
import { IsIn, IsString } from 'class-validator';
import { ApiProperty } from '@nestjs/swagger';

class UpdateLocaleDto {
  @ApiProperty({ enum: ['uz', 'ru'] })
  @IsString()
  @IsIn(['uz', 'ru'])
  declare locale: 'uz' | 'ru';
}

@ApiTags('users')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('users')
export class UsersController {
  constructor(private usersService: UsersService) {}

  @Get('me')
  getMe(@CurrentUser() user: any) {
    return this.usersService.findById(user.id);
  }

  @Get()
  listOrgUsers(@OrgId() orgId: string) {
    return this.usersService.findByOrgId(orgId);
  }

  @Patch('me/locale')
  updateLocale(@CurrentUser() user: any, @Body() dto: UpdateLocaleDto) {
    return this.usersService.updateLocale(user.id, dto.locale);
  }

  @Delete(':id')
  remove(@Param('id') id: string) {
    return this.usersService.remove(id);
  }
}
