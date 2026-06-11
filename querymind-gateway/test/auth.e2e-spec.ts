import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { getRepositoryToken } from '@nestjs/typeorm';
import { JwtService } from '@nestjs/jwt';
import { AppModule } from '../src/app.module';
import { GlobalExceptionFilter } from '../src/common/filters/global-exception.filter';
import { ResponseInterceptor } from '../src/common/interceptors/response.interceptor';
import { User } from '../src/entities/user.entity';
import { RequestLog } from '../src/entities/request-log.entity';

// Mocked repositories — avoids real DB in integration tests
const mockUserRepo = {
  findOne: jest.fn(),
  create: jest.fn(),
  save: jest.fn(),
  softDelete: jest.fn(),
};

const mockLogRepo = {
  save: jest.fn().mockResolvedValue({}),
};

const mockRedis = {
  get: jest.fn().mockResolvedValue(null),
  set: jest.fn().mockResolvedValue(undefined),
  incr: jest.fn().mockResolvedValue(1),
  expire: jest.fn().mockResolvedValue(undefined),
  ttl: jest.fn().mockResolvedValue(60),
  del: jest.fn().mockResolvedValue(undefined),
  quit: jest.fn().mockResolvedValue(undefined),
};

jest.mock('ioredis', () => {
  return jest.fn().mockImplementation(() => mockRedis);
});

describe('Auth Endpoints (e2e)', () => {
  let app: INestApplication;
  let jwtService: JwtService;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    })
      .overrideProvider(getRepositoryToken(User))
      .useValue(mockUserRepo)
      .overrideProvider(getRepositoryToken(RequestLog))
      .useValue(mockLogRepo)
      .compile();

    app = moduleFixture.createNestApplication();

    app.useGlobalPipes(
      new ValidationPipe({
        whitelist: true,
        forbidNonWhitelisted: true,
        transform: true,
        transformOptions: { enableImplicitConversion: true },
      }),
    );
    app.useGlobalFilters(new GlobalExceptionFilter());
    app.useGlobalInterceptors(new ResponseInterceptor());

    await app.init();

    jwtService = moduleFixture.get<JwtService>(JwtService);
  });

  afterAll(async () => {
    await app.close();
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('POST /api/v1/auth/register', () => {
    it('should register a new user', async () => {
      const newUser = {
        user_id: 'new-uuid',
        email: 'newuser@example.com',
        password_hash: 'hashed',
        deleted_at: null,
        created_at: new Date(),
      };

      mockUserRepo.findOne.mockResolvedValue(null);
      mockUserRepo.create.mockReturnValue(newUser);
      mockUserRepo.save.mockResolvedValue(newUser);

      const response = await request(app.getHttpServer())
        .post('/api/v1/auth/register')
        .send({ email: 'newuser@example.com', password: 'Password1!' })
        .expect(201);

      expect(response.body.success).toBe(true);
      expect(response.body.data).toHaveProperty('access_token');
      expect(response.body.data).toHaveProperty('refresh_token');
    });

    it('should return 400 on invalid email', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/auth/register')
        .send({ email: 'not-an-email', password: 'Password1!' })
        .expect(400);

      expect(response.body.success).toBe(false);
      expect(response.body.error.code).toBe('BAD_REQUEST');
    });

    it('should return 400 on weak password', async () => {
      const response = await request(app.getHttpServer())
        .post('/api/v1/auth/register')
        .send({ email: 'user@example.com', password: 'weak' })
        .expect(400);

      expect(response.body.success).toBe(false);
    });
  });

  describe('POST /api/v1/auth/login', () => {
    it('should return 401 on wrong credentials', async () => {
      mockUserRepo.findOne.mockResolvedValue(null);

      const response = await request(app.getHttpServer())
        .post('/api/v1/auth/login')
        .send({ email: 'nobody@example.com', password: 'Password1!' })
        .expect(401);

      expect(response.body.success).toBe(false);
      expect(response.body.error.code).toBe('UNAUTHORIZED');
    });
  });

  describe('GET /api/v1/users/profile', () => {
    it('should return 401 without token', async () => {
      await request(app.getHttpServer())
        .get('/api/v1/users/profile')
        .expect(401);
    });

    it('should return profile with valid token', async () => {
      const mockUser = {
        user_id: 'uuid-1234',
        email: 'test@example.com',
        created_at: new Date(),
      };

      mockUserRepo.findOne.mockResolvedValue(mockUser);

      const token = jwtService.sign({
        user_id: 'uuid-1234',
        email: 'test@example.com',
        type: 'access',
      });

      const response = await request(app.getHttpServer())
        .get('/api/v1/users/profile')
        .set('Authorization', `Bearer ${token}`)
        .expect(200);

      expect(response.body.success).toBe(true);
      expect(response.body.data).toHaveProperty('email', 'test@example.com');
    });
  });
});
