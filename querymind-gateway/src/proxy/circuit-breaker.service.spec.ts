import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { CircuitBreakerService } from './circuit-breaker.service';

const mockConfigService = {
  get: jest.fn((key: string) => {
    const map: Record<string, number> = {
      'proxy.circuitBreakerThreshold': 3,
      'proxy.circuitBreakerResetTimeout': 100,
    };
    return map[key];
  }),
};

describe('CircuitBreakerService', () => {
  let service: CircuitBreakerService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        CircuitBreakerService,
        { provide: ConfigService, useValue: mockConfigService },
      ],
    }).compile();

    service = module.get<CircuitBreakerService>(CircuitBreakerService);
  });

  it('should start in CLOSED state', () => {
    expect(service.getState()).toBe('CLOSED');
    expect(service.canExecute()).toBe(true);
  });

  it('should open after threshold failures', () => {
    service.recordFailure();
    service.recordFailure();
    expect(service.canExecute()).toBe(true);
    service.recordFailure();
    expect(service.getState()).toBe('OPEN');
    expect(service.canExecute()).toBe(false);
  });

  it('should transition to HALF_OPEN after reset timeout', async () => {
    service.recordFailure();
    service.recordFailure();
    service.recordFailure();
    expect(service.getState()).toBe('OPEN');

    await new Promise((r) => setTimeout(r, 150)); // wait past reset timeout

    expect(service.canExecute()).toBe(true);
    expect(service.getState()).toBe('HALF_OPEN');
  });

  it('should close again after successful test request', async () => {
    service.recordFailure();
    service.recordFailure();
    service.recordFailure();
    await new Promise((r) => setTimeout(r, 150));

    service.canExecute(); // transitions to HALF_OPEN
    service.recordSuccess();

    expect(service.getState()).toBe('CLOSED');
    expect(service.canExecute()).toBe(true);
  });

  it('should reset failure count on success', () => {
    service.recordFailure();
    service.recordFailure();
    service.recordSuccess();
    expect(service.getState()).toBe('CLOSED');
  });
});
