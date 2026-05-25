/**
 * API Gateway — RabbitMQ Event Contract
 * ======================================
 * This file declares every event the Gateway PUBLISHES to microservices
 * and the reply events it CONSUMES back. This is the TypeScript mirror of
 * the Python shared events.py and schemas.py.
 *
 * The Gateway PUBLISHES to these routing keys:
 *   schema.connect.request
 *   schema.disconnect.request
 *   schema.get.request
 *   schema.get_tables.request
 *   exec.init.request
 *   exec.run.request
 *   exec.history.request
 *   ai.query.generate.request
 *
 * The Gateway RECEIVES replies via amq.rabbitmq.reply-to (direct reply-to).
 * No temporary reply queues are created.
 *
 * WebSocket to AI Service:
 *   ws://ai-service:8002/ws/query/{session_id}  ← only direct connection retained
 */

export const EXCHANGE = 'querymind.events';

export const Events = {
  // Schema Service
  SCHEMA_CONNECT_REQUEST:    'schema.connect.request',
  SCHEMA_CONNECT_REPLY:      'schema.connect.reply',
  SCHEMA_GET_REQUEST:        'schema.get.request',
  SCHEMA_GET_REPLY:          'schema.get.reply',
  SCHEMA_GET_TABLES_REQUEST: 'schema.get_tables.request',
  SCHEMA_GET_TABLES_REPLY:   'schema.get_tables.reply',
  SCHEMA_REFRESH_REQUEST:    'schema.refresh.request',
  SCHEMA_DISCONNECT_REQUEST: 'schema.disconnect.request',
  SCHEMA_DISCONNECT_REPLY:   'schema.disconnect.reply',

  // AI Service
  AI_QUERY_GENERATE_REQUEST: 'ai.query.generate.request',
  AI_QUERY_GENERATE_REPLY:   'ai.query.generate.reply',

  // Execution Service
  EXEC_INIT_REQUEST:         'exec.init.request',
  EXEC_INIT_REPLY:           'exec.init.reply',
  EXEC_RUN_REQUEST:          'exec.run.request',
  EXEC_RUN_REPLY:            'exec.run.reply',
  EXEC_HISTORY_REQUEST:      'exec.history.request',
  EXEC_HISTORY_REPLY:        'exec.history.reply',
} as const;

export type EventKey = keyof typeof Events;
export type EventValue = (typeof Events)[EventKey];
