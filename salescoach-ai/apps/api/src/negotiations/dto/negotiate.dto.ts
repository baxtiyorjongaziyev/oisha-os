import { IsString, IsOptional, IsArray } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export enum NegotiationContext {
  INITIAL = 'initial',
  PRICING = 'pricing',
  OBJECTION = 'objection',
  CLOSING = 'closing',
  FOLLOWUP = 'followup',
}

export class NegotiateDto {
  @ApiProperty({ description: 'Customer message or transcript excerpt' })
  @IsString()
  message!: string;

  @ApiPropertyOptional({ description: 'Conversation history (last 5 turns)' })
  @IsArray()
  @IsOptional()
  history?: Array<{ role: 'manager' | 'customer'; content: string }>;

  @ApiPropertyOptional({ description: 'CRM lead status' })
  @IsString()
  @IsOptional()
  crmStatus?: string;

  @ApiPropertyOptional({ description: 'Service type (branding, web, marketing, consulting)' })
  @IsString()
  @IsOptional()
  serviceType?: string;

  @ApiPropertyOptional({ description: 'Customer name for personalization' })
  @IsString()
  @IsOptional()
  customerName?: string;

  @ApiPropertyOptional({ description: 'Call ID — if tied to a specific recorded call' })
  @IsString()
  @IsOptional()
  callId?: string;
}

export class RealtimeSuggestionDto {
  @ApiProperty({ description: 'Live transcript text from the ongoing call' })
  @IsString()
  message!: string;

  @ApiPropertyOptional()
  @IsString()
  @IsOptional()
  callId?: string;

  @ApiPropertyOptional()
  @IsString()
  @IsOptional()
  crmStatus?: string;
}
