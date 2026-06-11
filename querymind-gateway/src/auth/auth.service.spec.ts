import { Test, TestingModule } from '@nestjs/testing';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { UnauthorizedException, ConflictException } from '@nestjs/common';
import * as bcrypt from 'bcrypt';
import { AuthService } from './auth.service';
import { UsersService } from '../users/users.service';
import { User } from '../entities/user.entity';

const mockUser: User = {
  user_id: 'test-uuid-1234',
  email: 'test@example.com',
  password_hash: '$2b$12$hashedpassword',
  deleted_at: null,
  created_at: new Date(),
};

const mockUsersService = {
  createUser: jest.fn(),
  findByEmail: jest.fn(),
  findById: jest.fn(),
  updateUser: jest.fn(),
};

const mockJwtService = {
  sign: jest.fn(),
  verify: jest.fn(),
};

const mockConfigService = {
  get: jest.fn((key: string) => {
    const map: Record<string, unknown> = {
      'jwt.secret': 'test-secret-32-chars-minimum-len',
      'jwt.accessExpiry': 3600,
      'jwt.refreshExpiry': 604800,
    };
    return map[key];
  }),
};

describe('AuthService', () => {
  let service: AuthService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AuthService,
        { provide: UsersService, useValue: mockUsersService },
        { provide: JwtService, useValue: mockJwtService },
        { provide: ConfigService, useValue: mockConfigService },
      ],
    }).compile();

    service = module.get<AuthService>(AuthService);
    jest.clearAllMocks();
  });

  describe('register', () => {
    it('should create a user and return tokens', async () => {
      mockUsersService.createUser.mockResolvedValue(mockUser);
      mockJwtService.sign.mockReturnValueOnce('access-token').mockReturnValueOnce('refresh-token');

      const result = await service.register({
        email: 'test@example.com',
        password: 'Password1!',
      });

      expect(result.tokens.access_token).toBe('access-token');
      expect(result.tokens.refresh_token).toBe('refresh-token');
      expect(result.user).toEqual(mockUser);
      expect(mockUsersService.createUser).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'Password1!',
      });
    });

    it('should propagate ConflictException from UsersService', async () => {
      mockUsersService.createUser.mockRejectedValue(
        new ConflictException('Email already registered'),
      );

      await expect(
        service.register({ email: 'test@example.com', password: 'Password1!' }),
      ).rejects.toThrow(ConflictException);
    });
  });

  describe('login', () => {
    it('should return tokens on valid credentials', async () => {
      const hash = await bcrypt.hash('Password1!', 12);
      mockUsersService.findByEmail.mockResolvedValue({
        ...mockUser,
        password_hash: hash,
      });
      mockJwtService.sign
        .mockReturnValueOnce('access-token')
        .mockReturnValueOnce('refresh-token');

      const result = await service.login({
        email: 'test@example.com',
        password: 'Password1!',
      });

      expect(result.tokens.access_token).toBe('access-token');
    });

    it('should throw UnauthorizedException on wrong password', async () => {
      const hash = await bcrypt.hash('RightPassword1!', 12);
      mockUsersService.findByEmail.mockResolvedValue({
        ...mockUser,
        password_hash: hash,
      });

      await expect(
        service.login({ email: 'test@example.com', password: 'WrongPassword1!' }),
      ).rejects.toThrow(UnauthorizedException);
    });

    it('should throw UnauthorizedException when user not found', async () => {
      mockUsersService.findByEmail.mockResolvedValue(null);

      await expect(
        service.login({ email: 'nobody@example.com', password: 'Password1!' }),
      ).rejects.toThrow(UnauthorizedException);
    });
  });

  describe('refresh', () => {
    it('should return new tokens on valid refresh token', async () => {
      mockJwtService.verify.mockReturnValue({
        user_id: mockUser.user_id,
        email: mockUser.email,
        type: 'refresh',
      });
      mockUsersService.findById.mockResolvedValue(mockUser);
      mockJwtService.sign
        .mockReturnValueOnce('new-access-token')
        .mockReturnValueOnce('new-refresh-token');

      const result = await service.refresh('valid-refresh-token');

      expect(result.access_token).toBe('new-access-token');
      expect(result.refresh_token).toBe('new-refresh-token');
    });

    it('should throw if token type is not refresh', async () => {
      mockJwtService.verify.mockReturnValue({
        user_id: mockUser.user_id,
        email: mockUser.email,
        type: 'access',
      });

      await expect(service.refresh('access-token-used-as-refresh')).rejects.toThrow(
        UnauthorizedException,
      );
    });

    it('should throw if JWT verification fails', async () => {
      mockJwtService.verify.mockImplementation(() => {
        throw new Error('jwt expired');
      });

      await expect(service.refresh('expired-token')).rejects.toThrow(
        UnauthorizedException,
      );
    });
  });
});
