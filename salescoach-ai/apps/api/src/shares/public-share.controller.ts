import { Controller, Get, Query, HttpCode } from '@nestjs/common';
import { ApiOperation, ApiQuery, ApiTags } from '@nestjs/swagger';
import { SharesService } from './shares.service';

@ApiTags('public')
@Controller('public/share')
export class PublicShareController {
  constructor(private sharesService: SharesService) {}

  @Get()
  @HttpCode(200)
  @ApiOperation({
    summary: 'Resolve share link by token',
    description: 'Token is passed as query param (client reads from URL fragment and sends here)',
  })
  @ApiQuery({ name: 'token', required: true })
  @ApiQuery({ name: 'password', required: false })
  resolve(@Query('token') token: string, @Query('password') password?: string) {
    return this.sharesService.resolvePublic(token, password);
  }
}
