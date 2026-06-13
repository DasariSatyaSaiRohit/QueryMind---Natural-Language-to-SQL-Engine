export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_at: number; // Unix timestamp for access_token expiry
}

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export interface DBConnection {
  connection_id: string;
  db_name: string;
  connection_string: string;
  db_type: 'postgresql' | 'mysql' | 'sqlite';
  table_count: number;
  table_names: string[];
  last_accessed: string | null;
  created_at: string;
}

export interface QuerySession {
  session_id: string;
  connection_id: string;
  created_at: string;
}

export interface QueryResult {
  sql: string;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  execution_time_ms: number;
  chain_of_thought: string[];
}

export interface QueryHistoryItem {
  id: string;
  session_id: string;
  user_input: string;
  sql_query: string;
  status: 'success' | 'error';
  created_at: string;
  is_deleted: boolean;
}

export interface HistoryItem extends QueryHistoryItem {
  data: QueryHistoryItem[] | [];
}
export interface ApiError {
  message: string;
  code?: string;
}
