import { ApiPropertyOptional } from '@nestjs/swagger';
import { IsOptional, IsString, IsIn } from 'class-validator';

export class CreateCallDto {
  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  customerPhone?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  customerName?: string;

  @ApiPropertyOptional({ enum: ['INBOUND', 'OUTBOUND'] })
  @IsOptional()
  @IsIn(['INBOUND', 'OUTBOUND'])
  direction?: 'INBOUND' | 'OUTBOUND';

  @ApiPropertyOptional({ description: 'File extension: mp3, wav, ogg, m4a' })
  @IsOptional()
  @IsIn(['mp3', 'wav', 'ogg', 'm4a', 'webm'])
  ext?: string;

  @ApiPropertyOptional({ description: 'MIME type for presigned upload' })
  @IsOptional()
  @IsString()
  contentType?: string;
}
