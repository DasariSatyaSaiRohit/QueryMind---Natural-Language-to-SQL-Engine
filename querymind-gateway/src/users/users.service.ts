import {
  Injectable,
  ConflictException,
  NotFoundException,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import * as bcrypt from 'bcrypt';
import { User } from '../entities/user.entity';
import { RegisterRequestDto, UpdateProfileRequestDto } from '../auth/dto/auth.dto';

@Injectable()
export class UsersService {
  constructor(
    @InjectRepository(User)
    private readonly userRepository: Repository<User>,
  ) {}

  async findByEmail(email: string): Promise<User | null> {
    return this.userRepository.findOne({
      where: { email },
      withDeleted: false,
    });
  }

  async findById(userId: string): Promise<User | null> {
    return this.userRepository.findOne({
      where: { user_id: userId },
      withDeleted: false,
    });
  }

  async createUser(dto: RegisterRequestDto): Promise<User> {
    const existing = await this.findByEmail(dto.email);
    if (existing) {
      throw new ConflictException('Email already registered');
    }

    const user = this.userRepository.create({
      email: dto.email,
      password_hash: await bcrypt.hash(dto.password, 12),
    });

    return this.userRepository.save(user);
  }

  async updateUser(
    userId: string,
    dto: UpdateProfileRequestDto,
  ): Promise<User> {
    const user = await this.findById(userId);
    if (!user) {
      throw new NotFoundException('User not found');
    }

    if (dto.email && dto.email !== user.email) {
      const existing = await this.findByEmail(dto.email);
      if (existing) {
        throw new ConflictException('Email already in use');
      }
      user.email = dto.email;
    }

    return this.userRepository.save(user);
  }

  async softDeleteUser(userId: string): Promise<void> {
    await this.userRepository.softDelete({ user_id: userId });
  }
}
