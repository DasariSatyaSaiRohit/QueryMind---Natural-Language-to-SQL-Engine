import {
  Entity,
  Column,
  PrimaryGeneratedColumn,
  DeleteDateColumn,
  CreateDateColumn,
} from 'typeorm';
import { Exclude } from 'class-transformer';

@Entity('users')
export class User {
  @PrimaryGeneratedColumn('uuid')
  user_id!: string;

  @Column({ unique: true, length: 255 })
  email!: string;

  @Column({ length: 255 })
  @Exclude()
  password_hash!: string;

  @DeleteDateColumn({ nullable: true })
  @Exclude()
  deleted_at!: Date | null;

  @CreateDateColumn({ default: () => 'CURRENT_TIMESTAMP' })
  created_at!: Date;
}
