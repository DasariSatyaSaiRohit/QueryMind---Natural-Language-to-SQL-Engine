import {
  Column,
  CreateDateColumn,
  Entity,
  PrimaryGeneratedColumn,
} from 'typeorm';

@Entity('request_logs')
export class RequestLog {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ nullable: true })
  user_id: string;

  @Column()
  endpoint: string;

  @Column({ nullable: true })
  session_id: string;

  @Column({ nullable: true })
  status_code: number;

  @Column({ nullable: true })
  response_time_ms: number;

  @CreateDateColumn()
  created_at: Date;
}
