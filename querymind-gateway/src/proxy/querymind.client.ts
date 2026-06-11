import {
  Injectable,
  Logger,
  ServiceUnavailableException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';
import { CircuitBreakerService } from './circuit-breaker.service';

@Injectable()
export class QueryMindClient {
  private readonly logger = new Logger(QueryMindClient.name);
  private readonly httpClient: AxiosInstance;
  private readonly maxRetries: number;
  private readonly retryDelayBase: number;

  constructor(
    private configService: ConfigService,
    private circuitBreaker: CircuitBreakerService,
  ) {
    const baseURL = this.configService.get<string>('proxy.queryMindServiceUrl');
    const timeout =
      this.configService.get<number>('proxy.requestTimeout') ?? 30000;

    this.maxRetries =
      this.configService.get<number>('proxy.maxRetries') ?? 3;
    this.retryDelayBase =
      this.configService.get<number>('proxy.retryDelayBase') ?? 1000;

    this.httpClient = axios.create({ baseURL, timeout });
  }

  async get<T = unknown>(
    endpoint: string,
    params?: Record<string, unknown>,
    headers?: Record<string, string>,
  ): Promise<T> {
    return this.executeWithResilience<T>('GET', endpoint, undefined, {
      params,
      headers,
    });
  }

  async post<T = unknown>(
    endpoint: string,
    body?: unknown,
    config?: { headers?: Record<string, string> },
  ): Promise<T> {
    return this.executeWithResilience<T>('POST', endpoint, body, config);
  }

  async delete<T = unknown>(
    endpoint: string,
    body?: unknown,
    config?: { headers?: Record<string, string> },
  ): Promise<T> {
    return this.executeWithResilience<T>('DELETE', endpoint, body, config);
  }

  private async executeWithResilience<T>(
    method: string,
    endpoint: string,
    body?: unknown,
    config?: Partial<AxiosRequestConfig>,
  ): Promise<T> {
    if (!this.circuitBreaker.canExecute()) {
      throw new ServiceUnavailableException(
        'QueryMind Service is temporarily unavailable',
      );
    }

    let lastError: Error | null = null;

    // for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        const response = await this.httpClient.request<T>({
          method,
          url: endpoint,
          data: body,
          ...config,
        });

        this.circuitBreaker.recordSuccess();
        return response.data;
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
        this.logger.warn(
          `Request to ${endpoint} failed (attempt ${1}): ${lastError.message}`,
        );

        // if (attempt < this.maxRetries) {
        //   const delay = this.retryDelayBase * Math.pow(2, attempt);
        //   await this.sleep(delay);
        // }
      }
    // }

    this.circuitBreaker.recordFailure();
    throw new ServiceUnavailableException(
      `QueryMind Service unavailable after ${this.maxRetries} retries: ${lastError?.message}`,
    );
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
