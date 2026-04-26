import { ApiPropertyOptional } from '@nestjs/swagger';
import { IsBoolean, IsInt, IsOptional, IsString, Max, MaxLength, Min, MinLength } from 'class-validator';

export class CreateShareLinkDto {
  @ApiPropertyOptional({ default: 30 })
  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(365)
  expiresInDays?: number;

  @ApiPropertyOptional({ minLength: 4, maxLength: 64 })
  @IsOptional()
  @IsString()
  @MinLength(4)
  @MaxLength(64)
  password?: string;

  @ApiPropertyOptional({ default: false })
  @IsOptional()
  @IsBoolean()
  maskCustomerName?: boolean;
}
