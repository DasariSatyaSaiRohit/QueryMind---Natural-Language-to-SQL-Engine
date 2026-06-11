import { Test, TestingModule } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { ConflictException, NotFoundException } from '@nestjs/common';
import { UsersService } from './users.service';
import { User } from '../entities/user.entity';

const mockUser: User = {
  user_id: 'uuid-1234',
  email: 'test@example.com',
  password_hash: '$2b$12$hashed',
  deleted_at: null,
  created_at: new Date(),
};

const mockRepo = {
  findOne: jest.fn(),
  create: jest.fn(),
  save: jest.fn(),
  softDelete: jest.fn(),
};

describe('UsersService', () => {
  let service: UsersService;
  let repo: jest.Mocked<Repository<User>>;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        UsersService,
        { provide: getRepositoryToken(User), useValue: mockRepo },
      ],
    }).compile();

    service = module.get<UsersService>(UsersService);
    repo = module.get(getRepositoryToken(User));
    jest.clearAllMocks();
  });

  describe('findByEmail', () => {
    it('should return user when found', async () => {
      repo.findOne.mockResolvedValue(mockUser);
      const result = await service.findByEmail('test@example.com');
      expect(result).toEqual(mockUser);
    });

    it('should return null when not found', async () => {
      repo.findOne.mockResolvedValue(null);
      const result = await service.findByEmail('nobody@example.com');
      expect(result).toBeNull();
    });
  });

  describe('findById', () => {
    it('should return user when found', async () => {
      repo.findOne.mockResolvedValue(mockUser);
      const result = await service.findById('uuid-1234');
      expect(result).toEqual(mockUser);
    });

    it('should return null when not found', async () => {
      repo.findOne.mockResolvedValue(null);
      const result = await service.findById('nonexistent-id');
      expect(result).toBeNull();
    });
  });

  describe('createUser', () => {
    it('should create and return a user', async () => {
      repo.findOne.mockResolvedValue(null);
      repo.create.mockReturnValue(mockUser);
      repo.save.mockResolvedValue(mockUser);

      const result = await service.createUser({
        email: 'test@example.com',
        password: 'Password1!',
      });

      expect(result).toEqual(mockUser);
      expect(repo.create).toHaveBeenCalled();
      expect(repo.save).toHaveBeenCalled();
    });

    it('should throw ConflictException if email exists', async () => {
      repo.findOne.mockResolvedValue(mockUser);

      await expect(
        service.createUser({ email: 'test@example.com', password: 'Password1!' }),
      ).rejects.toThrow(ConflictException);
    });
  });

  describe('updateUser', () => {
    it('should update email and return user', async () => {
      const updated = { ...mockUser, email: 'new@example.com' };
      repo.findOne
        .mockResolvedValueOnce(mockUser) // findById
        .mockResolvedValueOnce(null);    // findByEmail (new email not taken)
      repo.save.mockResolvedValue(updated);

      const result = await service.updateUser('uuid-1234', {
        email: 'new@example.com',
      });

      expect(result.email).toBe('new@example.com');
    });

    it('should throw NotFoundException if user not found', async () => {
      repo.findOne.mockResolvedValue(null);

      await expect(
        service.updateUser('nonexistent', { email: 'x@example.com' }),
      ).rejects.toThrow(NotFoundException);
    });

    it('should throw ConflictException if new email is taken', async () => {
      repo.findOne
        .mockResolvedValueOnce(mockUser)        // findById
        .mockResolvedValueOnce({ ...mockUser, user_id: 'other-id' }); // findByEmail

      await expect(
        service.updateUser('uuid-1234', { email: 'taken@example.com' }),
      ).rejects.toThrow(ConflictException);
    });
  });
});
