import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { ServiceUnavailableException } from '@nestjs/common';
import axios from 'axios';
import { QueryMindClient } from './querymind.client';
import { CircuitBreakerService } from './circuit-breaker.service';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

const mockCircuitBreaker = {
  canExecute: jest.fn(),
  recordSuccess: jest.fn(),
  recordFailure: jest.fn(),
};

const mockConfigService = {
  get: jest.fn((key: string) => {
    const map: Record<string, unknown> = {
      'proxy.queryMindServiceUrl': 'http://querymind-service:8001/api/v1',
      'proxy.requestTimeout': 30000,
      'proxy.maxRetries': 2,
      'proxy.retryDelayBase': 10, // Short for tests
    };
    return map[key];
  }),
};

describe('QueryMindClient', () => {
  let client: QueryMindClient;
  let mockAxiosInstance: { request: jest.Mock };

  beforeEach(async () => {
    mockAxiosInstance = { request: jest.fn() };
    mockedAxios.create = jest.fn().mockReturnValue(mockAxiosInstance);

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        QueryMindClient,
        { provide: ConfigService, useValue: mockConfigService },
        { provide: CircuitBreakerService, useValue: mockCircuitBreaker },
      ],
    }).compile();

    client = module.get<QueryMindClient>(QueryMindClient);
    jest.clearAllMocks();
    mockCircuitBreaker.canExecute.mockReturnValue(true);
  });

  describe('get', () => {
    it('should make a GET request and return data', async () => {
      mockAxiosInstance.request.mockResolvedValue({ data: { result: 'ok' } });

      const result = await client.get('/connections/list', { user_id: 'uid' });

      expect(result).toEqual({ result: 'ok' });
      expect(mockCircuitBreaker.recordSuccess).toHaveBeenCalled();
    });
  });

  describe('post', () => {
    it('should make a POST request and return data', async () => {
      mockAxiosInstance.request.mockResolvedValue({ data: { id: '123' } });

      const result = await client.post('/connections/add', { name: 'test' });

      expect(result).toEqual({ id: '123' });
    });
  });

  describe('circuit breaker', () => {
    it('should throw ServiceUnavailableException when circuit is open', async () => {
      mockCircuitBreaker.canExecute.mockReturnValue(false);

      await expect(client.get('/any')).rejects.toThrow(ServiceUnavailableException);
    });
  });

  describe('retry logic', () => {
    it('should retry on failure and eventually throw', async () => {
      mockAxiosInstance.request.mockRejectedValue(new Error('Connection refused'));

      await expect(client.get('/any')).rejects.toThrow(ServiceUnavailableException);

      // maxRetries=2 means initial + 2 retries = 3 calls total
      expect(mockAxiosInstance.request).toHaveBeenCalledTimes(3);
      expect(mockCircuitBreaker.recordFailure).toHaveBeenCalled();
    });

    it('should succeed on retry after initial failure', async () => {
      mockAxiosInstance.request
        .mockRejectedValueOnce(new Error('Transient'))
        .mockResolvedValueOnce({ data: { ok: true } });

      const result = await client.get('/any');

      expect(result).toEqual({ ok: true });
      expect(mockCircuitBreaker.recordSuccess).toHaveBeenCalled();
    });
  });
});
