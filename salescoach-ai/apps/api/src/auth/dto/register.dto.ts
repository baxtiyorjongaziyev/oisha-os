import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsEmail, IsString, MinLength, MaxLength, IsOptional, IsIn } from 'class-validator';

export class RegisterDto {
  @ApiProperty()
  @IsEmail()
  email: string;

  @ApiProperty({ minLength: 8 })
  @IsString()
  @MinLength(8)
  @MaxLength(128)
  password: string;

  @ApiProperty({ description: 'Organization name' })
  @IsString()
  @MinLength(2)
  @MaxLength(100)
  orgName: string;

  @ApiPropertyOptional({ enum: ['uz', 'ru'] })
  @IsOptional()
  @IsIn(['uz', 'ru'])
  locale?: string;
}
