import {
  IsEmail,
  IsString,
  MinLength,
  MaxLength,
  Matches,
  IsOptional,
  IsUUID,
  IsInt,
  Min,
  Max,
} from 'class-validator';
import { Transform } from 'class-transformer';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class RegisterRequestDto {
  @ApiProperty({ example: 'user@example.com' })
  @IsEmail({}, { message: 'Invalid email format' })
  @Transform(({ value }: { value: string; }) => value?.trim().toLowerCase())
  email!: string;

  @ApiProperty({ minLength: 8, maxLength: 128 })
  @IsString()
  @MinLength(8, { message: 'Password must be at least 8 characters' })
  @MaxLength(128, { message: 'Password too long' })
  @Matches(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/, {
    message: 'Password must contain uppercase, lowercase, number, and special character',
  })

  @Transform(({ value }: { value: string; }) => value?.trim())
  password!: string;
}

export class LoginRequestDto {
  @ApiProperty({ example: 'user@example.com' })
  @IsEmail({}, { message: 'Invalid email format' })
  @Transform(({ value }: { value: string; }) => value?.trim().toLowerCase())
  email!: string;

  @ApiProperty()
  @IsString()
  @MinLength(1, { message: 'Password is required' })
  @Transform(({ value }: { value: string; }) => value?.trim())
  password!: string;
}

export class RefreshTokenDto {
  @ApiProperty()
  @IsString()
  @MinLength(1, { message: 'Refresh token is required' })
  refresh_token!: string;
}

export class UpdateProfileRequestDto {
  @ApiPropertyOptional({ example: 'new@example.com' })
  @IsOptional()
  @IsEmail({}, { message: 'Invalid email format' })
  @Transform(({ value }: { value: string }) => value?.trim().toLowerCase())
  email?: string;
}

export class  ForwardRequestDto {
  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @Transform(({ value }: { value: string }) => value?.trim())
  connection_id?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @Transform(({ value }: { value: string }) => value?.trim())
  question?: string;

  @ApiPropertyOptional()
  @IsOptional()
  // @IsUUID()
  @Transform(({ value }: { value: string }) => value?.trim())
  session_id?: string;

  @ApiPropertyOptional({ default: 1, minimum: 1 })
  @IsOptional()
  @IsInt()
  @Min(1, { message: 'Page must be at least 1' })
  page?: number = 1;

  @ApiPropertyOptional({ default: 50, minimum: 1, maximum: 200 })
  @IsOptional()
  @IsInt()
  @Min(1, { message: 'Page size must be at least 1' })
  @Max(200, { message: 'Page size max is 200' })
  page_size?: number = 50;
}
