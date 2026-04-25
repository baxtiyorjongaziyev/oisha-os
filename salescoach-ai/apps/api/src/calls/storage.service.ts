import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { S3Client, PutObjectCommand, GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

@Injectable()
export class StorageService {
  private readonly s3: S3Client;
  private readonly bucket: string;

  constructor(private cfg: ConfigService) {
    this.bucket = cfg.getOrThrow('S3_BUCKET');
    const endpoint = cfg.get<string>('S3_ENDPOINT');
    this.s3 = new S3Client({
      region: cfg.get('AWS_REGION', 'us-east-1'),
      ...(endpoint ? { endpoint, forcePathStyle: cfg.get('S3_FORCE_PATH_STYLE', 'false') === 'true' } : {}),
      credentials: {
        accessKeyId: cfg.getOrThrow('AWS_ACCESS_KEY_ID'),
        secretAccessKey: cfg.getOrThrow('AWS_SECRET_ACCESS_KEY'),
      },
    });
  }

  async presignedUpload(key: string, contentType: string, expiresIn = 300) {
    const cmd = new PutObjectCommand({ Bucket: this.bucket, Key: key, ContentType: contentType });
    return getSignedUrl(this.s3, cmd, { expiresIn });
  }

  async presignedDownload(key: string, expiresIn = 3600) {
    const cmd = new GetObjectCommand({ Bucket: this.bucket, Key: key });
    return getSignedUrl(this.s3, cmd, { expiresIn });
  }
}
