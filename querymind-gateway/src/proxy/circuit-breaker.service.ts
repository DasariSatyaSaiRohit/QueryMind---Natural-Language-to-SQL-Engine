import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

enum CircuitState {
  CLOSED = 'CLOSED',   // Normal operation
  OPEN = 'OPEN',       // Failing — reject all
  HALF_OPEN = 'HALF_OPEN', // Testing one request
}

@Injectable()
export class CircuitBreakerService {
  private readonly logger = new Logger(CircuitBreakerService.name);
  private state: CircuitState = CircuitState.CLOSED;
  private failureCount = 0;
  private lastFailureTime: number | null = null;

  private readonly threshold: number;
  private readonly resetTimeout: number;

  constructor(private configService: ConfigService) {
    this.threshold = this.configService.get<number>(
      'proxy.circuitBreakerThreshold',
    ) ?? 5;
    this.resetTimeout = this.configService.get<number>(
      'proxy.circuitBreakerResetTimeout',
    ) ?? 60000;
  }

  canExecute(): boolean {
    if (this.state === CircuitState.CLOSED) return true;

    if (this.state === CircuitState.OPEN) {
      if (
        this.lastFailureTime &&
        Date.now() - this.lastFailureTime >= this.resetTimeout
      ) {
        this.logger.log('Circuit breaker transitioning to HALF_OPEN');
        this.state = CircuitState.HALF_OPEN;
        return true;
      }
      return false;
    }

    // HALF_OPEN: allow one test request through
    return true;
  }

  recordSuccess(): void {
    if (this.state === CircuitState.HALF_OPEN) {
      this.logger.log('Circuit breaker CLOSED after successful test request');
    }
    this.state = CircuitState.CLOSED;
    this.failureCount = 0;
    this.lastFailureTime = null;
  }

  recordFailure(): void {
    this.failureCount++;
    this.lastFailureTime = Date.now();

    if (
      this.state === CircuitState.HALF_OPEN ||
      this.failureCount >= this.threshold
    ) {
      this.logger.warn(
        `Circuit breaker OPEN after ${this.failureCount} failures`,
      );
      this.state = CircuitState.OPEN;
    }
  }

  getState(): CircuitState {
    return this.state;
  }
}
