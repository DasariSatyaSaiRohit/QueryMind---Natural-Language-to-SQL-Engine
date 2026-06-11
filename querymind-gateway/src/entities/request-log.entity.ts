import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  DeleteDateColumn,
  CreateDateColumn,
} from 'typeorm';

@Entity('request_logs')
export class RequestLog {
  @PrimaryGeneratedColumn('uuid')
  log_id!: string;

  @Column()
  request_id!: string;

  @Column()
  correlation_id!: string;

  @Column()
  user_id!: string;

  @Column({ length: 10 })
  method!: string;

  @Column({ length: 500 })
  path!: string;

  @Column({ type: 'int', default: 0 })
  status_code!: number;

  @Column({ type: 'int', default: 0 })
  duration_ms!: number;

  @DeleteDateColumn({ nullable: true })
  deleted_at!: Date | null;

  @CreateDateColumn({ default: () => 'CURRENT_TIMESTAMP' })
  timestamp!: Date;
}
