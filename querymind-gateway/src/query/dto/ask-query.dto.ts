import { IsString, IsNotEmpty } from 'class-validator';

export class AskQueryDto {
  @IsString()
  @IsNotEmpty()
  session_id: string;

  @IsString()
  @IsNotEmpty()
  question: string;
}
