import { Type } from 'class-transformer';
import {
  ArrayMaxSize,
  ArrayMinSize,
  IsArray,
  IsEnum,
  IsInt,
  IsISO8601,
  IsOptional,
  IsString,
  MaxLength,
  MinLength,
  ValidateNested,
} from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export enum ConversationRole {
  MANAGER = 'manager',
  CUSTOMER = 'customer',
}

export class ConversationMessageDto {
  @ApiProperty({ description: 'Telegram message ID used as evidence' })
  @IsInt()
  id!: number;

  @ApiProperty({ enum: ConversationRole })
  @IsEnum(ConversationRole)
  role!: ConversationRole;

  @ApiProperty({ description: 'Plain-text message or voice-note transcript' })
  @IsString()
  @MinLength(1)
  @MaxLength(4000)
  text!: string;

  @ApiProperty({ description: 'ISO-8601 Telegram message timestamp' })
  @IsISO8601()
  sentAt!: string;
}

export class AnalyzeConversationDto {
  @ApiProperty({ description: 'Matched AmoCRM lead ID' })
  @IsInt()
  leadId!: number;

  @ApiProperty({ description: 'AmoCRM responsible manager ID' })
  @IsString()
  @MinLength(1)
  managerId!: string;

  @ApiPropertyOptional({ description: 'Current AmoCRM lead status' })
  @IsOptional()
  @IsString()
  @MaxLength(250)
  crmStatus?: string;

  @ApiProperty({
    type: [ConversationMessageDto],
    minItems: 2,
    maxItems: 50,
    description: 'Chronological manager/customer Telegram messages',
  })
  @IsArray()
  @ArrayMinSize(2)
  @ArrayMaxSize(50)
  @ValidateNested({ each: true })
  @Type(() => ConversationMessageDto)
  messages!: ConversationMessageDto[];
}
