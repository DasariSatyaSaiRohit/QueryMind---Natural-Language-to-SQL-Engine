import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { User } from './user.entity';

@Injectable()
export class UsersService {
  constructor(
    @InjectRepository(User)
    private readonly usersRepo: Repository<User>,
  ) {}

  async findByEmail(email: string): Promise<User | null> {
    return this.usersRepo.findOne({ where: { email } });
  }

  async findById(userId: string): Promise<User | null> {
    return this.usersRepo.findOne({ where: { user_id: userId } });
  }

  async create(email: string, passwordHash: string): Promise<User> {
    const user = this.usersRepo.create({ email, password_hash: passwordHash });
    return this.usersRepo.save(user);
  }
}
