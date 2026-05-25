import { IsInt, IsNotEmpty, IsOptional, IsString, Max, Min } from 'class-validator';

export class ExecuteOnlyDto {
  @IsString()
  @IsNotEmpty()
  session_id: string;

  @IsString()
  @IsNotEmpty()
  sql: string;

  @IsOptional()
  @IsInt()
  @Min(1)
  page?: number = 1;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(200)
  page_size?: number = 50;
}
