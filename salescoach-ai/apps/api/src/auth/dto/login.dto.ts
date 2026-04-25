import { ApiProperty } from '@nestjs/swagger';
import { IsEmail, IsString } from 'class-validator';

export class LoginDto {
  @ApiProperty()
  @IsEmail()
  declare email: string;

  @ApiProperty()
  @IsString()
  declare password: string;
}
