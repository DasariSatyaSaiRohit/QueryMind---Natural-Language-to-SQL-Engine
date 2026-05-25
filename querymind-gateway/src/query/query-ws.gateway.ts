import { Logger } from '@nestjs/common';
import * as http from 'http';
import * as url from 'url';
import * as WebSocket from 'ws';
import { AuthService } from '../auth/auth.service';

/**
 * WebSocket proxy from frontend to the AI Service streaming endpoint.
 * This is the ONLY direct connection to a microservice retained in the gateway.
 * WebSocket streaming cannot cleanly go through RabbitMQ without added buffering complexity.
 *
 * The proxy is set up manually using the 'ws' library — NOT @nestjs/websockets —
 * because we need a transparent bidirectional proxy, not a NestJS event handler.
 */
export class QueryWsGateway {
  private readonly logger = new Logger(QueryWsGateway.name);
  private wss: WebSocket.Server;
  private readonly aiServiceWsUrl: string;
  // Track active upstream connections per user for concurrency limiting
  private userConnections = new Map<string, Set<WebSocket>>();
  private readonly MAX_CONNECTIONS_PER_USER = 3;

  constructor(private readonly authService: AuthService) {
    this.aiServiceWsUrl =
      process.env.AI_SERVICE_WS_URL || 'ws://localhost:8002';
  }

  /**
   * Attach the WebSocket server to an existing HTTP server.
   * Called from main.ts after the NestJS app has been set up.
   */
  attach(server: http.Server): void {
    this.wss = new WebSocket.Server({ server, path: '/ws/query' });

    this.wss.on('connection', (clientWs: WebSocket, req: http.IncomingMessage) => {
      this.handleConnection(clientWs, req);
    });

    this.logger.log('WebSocket proxy attached — listening on /ws/query/:session_id');
  }

  private handleConnection(clientWs: WebSocket, req: http.IncomingMessage): void {
    const parsedUrl = url.parse(req.url || '', true);
    // Extract session_id from path: /ws/query/{session_id}
    const pathParts = (parsedUrl.pathname || '').split('/').filter(Boolean);
    const sessionId = pathParts[2]; // ['ws', 'query', '{session_id}']
    const token = parsedUrl.query.token as string;

    // Validate JWT
    if (!token) {
      this.logger.warn('WS connection rejected: no token provided');
      clientWs.close(4001, 'Authentication required');
      return;
    }

    const payload = this.authService.verifyToken(token);
    if (!payload || payload.type !== 'access') {
      this.logger.warn('WS connection rejected: invalid token');
      clientWs.close(4001, 'Invalid or expired token');
      return;
    }

    const userId = payload.sub;

    // Enforce max concurrent connections per user
    if (!this.userConnections.has(userId)) {
      this.userConnections.set(userId, new Set());
    }
    const userSet = this.userConnections.get(userId)!;
    if (userSet.size >= this.MAX_CONNECTIONS_PER_USER) {
      this.logger.warn(`WS connection rejected for user ${userId}: max concurrent connections reached`);
      clientWs.close(4029, 'Too many concurrent WebSocket connections');
      return;
    }

    if (!sessionId) {
      clientWs.close(4000, 'session_id is required in path: /ws/query/{session_id}');
      return;
    }

    this.logger.log(`WS proxy connect: user=${userId} session=${sessionId}`);

    // Open upstream connection to AI Service
    const upstreamUrl = `${this.aiServiceWsUrl}/ws/query/${sessionId}`;
    const upstreamWs = new WebSocket(upstreamUrl);

    userSet.add(clientWs);

    const cleanup = () => {
      userSet.delete(clientWs);
      if (upstreamWs.readyState === WebSocket.OPEN) {
        upstreamWs.close();
      }
    };

    // Upstream open — ready to proxy
    upstreamWs.on('open', () => {
      this.logger.debug(`Upstream WS opened for session ${sessionId}`);
    });

    // Upstream → Client (streaming tokens, complete, error)
    upstreamWs.on('message', (data: WebSocket.RawData) => {
      if (clientWs.readyState === WebSocket.OPEN) {
        clientWs.send(data.toString());
      }
    });

    // Client → Upstream (question payload)
    clientWs.on('message', (data: WebSocket.RawData) => {
      if (upstreamWs.readyState === WebSocket.OPEN) {
        upstreamWs.send(data.toString());
      } else {
        // Upstream not ready yet — buffer or notify
        this.logger.warn(`Upstream not ready for session ${sessionId}, dropping client message`);
      }
    });

    // Upstream disconnect
    upstreamWs.on('close', (code, reason) => {
      this.logger.debug(`Upstream WS closed for session ${sessionId}: ${code}`);
      if (clientWs.readyState === WebSocket.OPEN) {
        clientWs.send(JSON.stringify({
          type: 'error',
          error: 'upstream_disconnected',
          message: 'AI service connection was lost.',
        }));
        clientWs.close();
      }
      cleanup();
    });

    upstreamWs.on('error', (err) => {
      this.logger.error(`Upstream WS error for session ${sessionId}: ${err.message}`);
      if (clientWs.readyState === WebSocket.OPEN) {
        clientWs.send(JSON.stringify({
          type: 'error',
          error: 'upstream_error',
          message: 'Failed to connect to AI service.',
        }));
        clientWs.close();
      }
      cleanup();
    });

    // Client disconnect
    clientWs.on('close', () => {
      this.logger.debug(`Client WS closed for session ${sessionId}`);
      cleanup();
    });

    clientWs.on('error', (err) => {
      this.logger.error(`Client WS error for session ${sessionId}: ${err.message}`);
      cleanup();
    });
  }
}
