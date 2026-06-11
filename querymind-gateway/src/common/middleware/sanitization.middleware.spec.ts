import { SanitizationMiddleware } from './sanitization.middleware';
import { Request, Response } from 'express';

describe('SanitizationMiddleware', () => {
  let middleware: SanitizationMiddleware;
  let mockNext: jest.Mock;

  beforeEach(() => {
    middleware = new SanitizationMiddleware();
    mockNext = jest.fn();
  });

  const makeReq = (overrides: Partial<Request> = {}) =>
    ({
      body: {},
      query: {},
      params: {},
      ...overrides,
    }) as unknown as Request;

  it('should call next()', () => {
    middleware.use(makeReq(), {} as Response, mockNext);
    expect(mockNext).toHaveBeenCalled();
  });

  it('should trim string values in body', () => {
    const req = makeReq({ body: { email: '  test@example.com  ' } });
    middleware.use(req, {} as Response, mockNext);
    expect(req.body.email).toBe('test@example.com');
  });

  it('should remove null bytes', () => {
    const req = makeReq({ body: { name: 'test\x00name' } });
    middleware.use(req, {} as Response, mockNext);
    expect(req.body.name).toBe('testname');
  });

  it('should remove control characters', () => {
    const req = makeReq({ body: { value: 'clean\x01dirty' } });
    middleware.use(req, {} as Response, mockNext);
    expect(req.body.value).toBe('cleandirty');
  });

  it('should preserve newline and tab', () => {
    const req = makeReq({ body: { text: 'line1\nline2\ttab' } });
    middleware.use(req, {} as Response, mockNext);
    expect(req.body.text).toBe('line1\nline2\ttab');
  });

  it('should sanitize nested objects', () => {
    const req = makeReq({ body: { nested: { key: '  value  ' } } });
    middleware.use(req, {} as Response, mockNext);
    expect(req.body.nested.key).toBe('value');
  });

  it('should sanitize arrays', () => {
    const req = makeReq({ body: { arr: [' a ', ' b '] } });
    middleware.use(req, {} as Response, mockNext);
    expect(req.body.arr).toEqual(['a', 'b']);
  });

  it('should sanitize query parameters', () => {
    const req = makeReq({ query: { search: '  hello  ' } });
    middleware.use(req, {} as Response, mockNext);
    expect(req.query.search).toBe('hello');
  });

  it('should handle non-string values passthrough', () => {
    const req = makeReq({ body: { count: 42, active: true } });
    middleware.use(req, {} as Response, mockNext);
    expect(req.body.count).toBe(42);
    expect(req.body.active).toBe(true);
  });
});
