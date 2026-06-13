# QueryMind - Natural Language to SQL Engine

![GitHub License](https://img.shields.io/badge/license-MIT-blue)
![Node.js](https://img.shields.io/badge/node.js-v20%2B-green)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)
![NestJS](https://img.shields.io/badge/NestJS-10-red)
![React](https://img.shields.io/badge/React-18-61DAFB)

QueryMind is a sophisticated full-stack application that converts natural language queries into SQL statements using AI. It provides a seamless interface for users to interact with databases through conversational language, powered by large language models like Ollama with fallback to HuggingFace.

## 🎯 Overview

QueryMind bridges the gap between natural language and databases, allowing users to query their data sources without SQL expertise. The system intelligently handles database schema introspection, SQL generation with validation, and secure query execution with comprehensive history tracking.

### Key Highlights

- **Natural Language Processing**: Convert plain English to SQL queries
- **Multi-Database Support**: PostgreSQL, MySQL, SQLite compatibility
- **Secure Architecture**: End-to-end encryption, request sanitization, SQL injection prevention
- **High Performance**: Redis caching, async operations, non-blocking query execution
- **Complete Audit Trail**: Query history with execution tracking and logging
- **Enterprise-Ready**: JWT authentication, rate limiting, health checks
- **Microservices Design**: Scalable service architecture with async task processing

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend (Port 3000)               │
│                    (Dashboard & Query UI)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/REST
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         NestJS API Gateway (Port 8000)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ • User Authentication (JWT)                         │  │
│  │ • Session Management                                │  │
│  │ • Rate Limiting & Request Validation                │  │
│  │ • Circuit Breaker Pattern                           │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/REST
                           ▼
┌──────────────────────────────────────────────────────────────┐
│         FastAPI Query Service (Port 8001)                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ • SQL Generation & Validation                        │ │
│  │ • Query Execution & Result Pagination                │ │
│  │ • Schema Introspection & Caching                     │ │
│  │ • Non-blocking History Persistence                   │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────┬──────────────────────────────────┬────────────┘
               │                                  │
        ┌──────▼─────┐              ┌────────────▼────────┐
        │  PostgreSQL │              │   Redis Cache      │
        │ (Metadata   │              │   & Sessions       │
        │  & History) │              │                    │
        └─────────────┘              └────────────────────┘
               │
        ┌──────▼──────────────────────────────┐
        │     RabbitMQ Message Queue           │
        │  (History Persistence Pipeline)      │
        └──────────┬─────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │  Celery Workers     │
        │  (Async Tasks)      │
        └─────────────────────┘
               │
        ┌──────▼─────────────────────────────┐
        │  External Services                 │
        │  • Ollama (Local LLM)              │
        │  • HuggingFace (Fallback)          │
        │  • User Databases (PostgreSQL,    │
        │    MySQL, SQLite, etc.)           │
        └────────────────────────────────────┘
```

## 🚀 Features

### 1. **Intelligent Query Generation**
   - Converts natural language questions to SQL queries
   - Context-aware schema understanding
   - Automatic query validation and safety checks
   - Fallback mechanisms for reliability

### 2. **Secure Data Access**
   - Connection string encryption (Fernet cipher)
   - SQL injection prevention with query validation
   - SELECT-only query enforcement
   - Request sanitization and input validation

### 3. **Performance Optimization**
   - Redis-based schema caching
   - Pagination support for large result sets
   - Connection pooling with async drivers
   - Non-blocking async request handling

### 4. **Comprehensive Monitoring**
   - Request ID tracking across services
   - Structured logging with contextual information
   - Health checks and readiness probes
   - Query execution history with timestamps

### 5. **User Management**
   - JWT-based authentication
   - User session management
   - Connection management per user
   - Access control and authorization

### 6. **Advanced Architecture**
   - Microservices design with independent scaling
   - Async task processing with Celery
   - Message queue integration (RabbitMQ)
   - Circuit breaker pattern for resilience

## 💻 Tech Stack

### Frontend
- **React** 18+ - UI framework
- **React Router** 6+ - Client-side routing
- **Zustand** - State management
- **TailwindCSS** - Utility-first CSS
- **TypeScript** - Type safety
- **Vite** - Build tool

### Backend (API Gateway)
- **NestJS** 10+ - Progressive Node.js framework
- **TypeORM** - ORM with PostgreSQL
- **JWT** - Authentication
- **Passport** - Authorization
- **Redis** - Caching and sessions
- **Winston** - Structured logging

### Backend (Query Service)
- **FastAPI** - Modern async Python framework
- **SQLAlchemy** - SQL toolkit and ORM
- **Alembic** - Database migrations
- **Celery** - Task queue
- **Redis** - Caching
- **Cryptography** - Encryption

### Infrastructure
- **PostgreSQL** - Primary database
- **Redis** - Cache and session store
- **RabbitMQ** - Message broker
- **Ollama** - Local LLM
- **Docker & Docker Compose** - Containerization

## 📁 Project Structure

```
querymind/
├── querymind-gateway/          # NestJS API Gateway
│   ├── src/
│   │   ├── auth/               # Authentication & JWT
│   │   ├── proxy/              # Service proxy & circuit breaker
│   │   ├── users/              # User management
│   │   ├── common/             # Guards, filters, middleware
│   │   ├── entities/           # Database entities
│   │   └── migrations/         # TypeORM migrations
│   ├── test/                   # E2E tests
│   ├── package.json
│   └── tsconfig.json
│
├── querymind-service/          # FastAPI Query Service
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/      # Route handlers
│   │   │   └── router.py       # API routes
│   │   ├── core/               # Config, logging, security
│   │   ├── db/                 # Database & Redis
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic models
│   │   ├── services/           # Business logic
│   │   ├── middleware/         # Request middleware
│   │   └── workers/            # Celery & RabbitMQ
│   ├── alembic/                # Database migrations
│   ├── rabbitmq_consumer.py    # Message consumer
│   ├── requirements.txt
│   └── Dockerfile
│
├── querymind_ui/               # React Frontend
│   ├── src/
│   │   ├── components/         # React components
│   │   ├── pages/              # Page components
│   │   ├── stores/             # Zustand stores
│   │   ├── types/              # TypeScript types
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── docker-compose.yml          # Full stack orchestration
└── README.md                   # This file
```

## 📋 Prerequisites

- **Node.js** 18+ (for gateway and frontend)
- **Python** 3.9+ (for query service)
- **Docker** & **Docker Compose** (for containerized setup)
- **PostgreSQL** 12+ (or hosted instance)
- **Redis** 6+ (or hosted instance)
- **RabbitMQ** 3.8+ (or hosted instance)
- **Ollama** (optional, for local LLM; HuggingFace fallback available)

## 🔧 Installation & Setup

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/querymind.git
cd querymind

# Create environment files
cp querymind-gateway/.env.example querymind-gateway/.env
cp querymind-service/.env.example querymind-service/.env

# Edit .env files with your configuration
nano querymind-gateway/.env
nano querymind-service/.env

# Start all services
docker compose up -d

# Run migrations
docker compose exec querymind-gateway npm run migration:run
docker compose exec querymind-service alembic upgrade head
```

### Option 2: Local Development Setup

#### Gateway Service
```bash
cd querymind-gateway

# Install dependencies
npm install

# Configure environment
cp .env.example .env

# Run migrations
npm run migration:run

# Start development server
npm run start:dev
```

#### Query Service
```bash
cd querymind-service

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Run migrations
alembic upgrade head

# Start Celery worker (in another terminal)
celery -A app.workers.celery_app worker --loglevel=info

# Start RabbitMQ consumer (in another terminal)
python rabbitmq_consumer.py

# Start the service
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

#### Frontend
```bash
cd querymind_ui

# Install dependencies
npm install

# Start development server
npm run dev
```

## 🌐 API Endpoints

### Authentication (Gateway - Port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Register new user |
| `POST` | `/auth/login` | Login and get JWT token |
| `POST` | `/auth/refresh` | Refresh JWT token |

### Connections Management (Gateway - Port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/connections` | List user's connections |
| `POST` | `/connections` | Create new database connection |
| `GET` | `/connections/:id` | Get connection details |
| `PUT` | `/connections/:id` | Update connection |
| `DELETE` | `/connections/:id` | Delete connection |

### Query Operations (Gateway - Port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/query/ask` | Generate and execute SQL from natural language |
| `GET` | `/query/history` | Get query execution history |
| `POST` | `/query/explain` | Get explanation of generated SQL |

### Health & Status (Service - Port 8001)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Liveness probe |
| `GET` | `/api/v1/health/ready` | Readiness check (all dependencies) |

## 📚 Usage Examples

### 1. Register & Login

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "secure_password",
    "name": "John Doe"
  }'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "secure_password"
  }'
```

### 2. Add Database Connection

```bash
curl -X POST http://localhost:8000/connections \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production DB",
    "type": "postgresql",
    "host": "db.example.com",
    "port": 5432,
    "database": "myapp",
    "username": "dbuser",
    "password": "dbpassword"
  }'
```

### 3. Execute Natural Language Query

```bash
curl -X POST http://localhost:8000/query/ask \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connectionId": "conn-123",
    "question": "Show me the top 10 customers by total purchases in the last month",
    "limit": 10
  }'

# Response
{
  "queryId": "q-789",
  "sql": "SELECT customer_id, SUM(amount) as total FROM orders WHERE date >= NOW() - INTERVAL 1 MONTH GROUP BY customer_id ORDER BY total DESC LIMIT 10",
  "results": [
    { "customer_id": 1, "total": 15000 },
    { "customer_id": 2, "total": 12500 },
    ...
  ],
  "executionTime": 245,
  "rowCount": 10
}
```

### 4. Query Execution History

```bash
curl -X GET http://localhost:8000/query/history \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Response
{
  "queries": [
    {
      "id": "q-789",
      "question": "Show me the top 10 customers...",
      "sql": "SELECT ...",
      "status": "success",
      "executedAt": "2024-06-13T10:30:00Z",
      "executionTime": 245
    }
  ],
  "total": 1,
  "page": 1
}
```

## 🔐 Security Features

### Data Protection
- **Encryption at Rest**: Database connections encrypted with Fernet cipher
- **Encryption in Transit**: TLS/HTTPS for all API communications
- **Credential Management**: Secure storage and retrieval of database credentials

### Access Control
- **JWT Authentication**: Token-based user authentication
- **Authorization**: Role-based access control (planned)
- **Rate Limiting**: Request throttling per user/IP
- **Session Management**: Secure session handling with timeout

### Query Safety
- **SQL Injection Prevention**: Input validation and parameterized queries
- **SELECT-Only Enforcement**: Prevents write/delete operations
- **Schema Validation**: Ensures tables/columns exist before execution
- **Request Sanitization**: XSS prevention and input cleaning
- **Audit Logging**: Complete query history and execution tracking

## 🚀 Deployment

### Production Deployment with Docker

```bash
# Build images
docker compose -f docker-compose.yml build

# Start services with production settings
docker compose -f docker-compose.yml up -d

# Check service health
curl http://localhost:8000/health
curl http://localhost:8001/api/v1/health/ready
```

### Environment Variables

#### Gateway (.env)
```
NODE_ENV=production
DATABASE_URL=postgresql://user:password@postgres:5432/querymind_gateway
REDIS_URL=redis://redis:6379
JWT_SECRET=your-secret-key-here
JWT_EXPIRATION=7d
SERVICE_URL=http://querymind-service:8001
ENCRYPTION_KEY=your-encryption-key
```

#### Query Service (.env)
```
ENVIRONMENT=production
DATABASE_URL=postgresql://user:password@postgres:5432/querymind_service
REDIS_URL=redis://redis:6379
AMQP_URL=amqp://user:password@rabbitmq:5672/
OLLAMA_URL=http://ollama:11434
ENCRYPTION_KEY=your-encryption-key
LOG_LEVEL=info
```

## 📊 Monitoring & Logging

### Health Checks
```bash
# Gateway health
curl http://localhost:8000/health

# Service health
curl http://localhost:8001/api/v1/health
curl http://localhost:8001/api/v1/health/ready
```

### Logs
```bash
# Gateway logs
docker compose logs -f querymind-gateway

# Service logs
docker compose logs -f querymind-service

# Worker logs
docker compose logs -f querymind-celery
```

### Metrics
- Request latency tracking
- Database query execution times
- Cache hit/miss ratios
- Worker task completion rates

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Setup Development Environment
```bash
# Clone and install
git clone https://github.com/yourusername/querymind.git
cd querymind
npm install --workspaces
```

### Code Standards
- **Backend**: Follow NestJS and FastAPI conventions
- **Frontend**: Follow React and TypeScript best practices
- **Format**: Use Prettier and ESLint
- **Tests**: Maintain >80% code coverage

### Commit Guidelines
```bash
git checkout -b feature/your-feature-name
# Make changes and commit
git add .
git commit -m "feat: description of changes"
git push origin feature/your-feature-name
```

### Running Tests
```bash
# Gateway tests
cd querymind-gateway
npm run test

# Frontend tests
cd querymind_ui
npm run test

# Service tests
cd querymind-service
pytest
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙋 Support & Community

- **Issues**: [GitHub Issues](https://github.com/yourusername/querymind/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/querymind/discussions)
- **Documentation**: [Full Documentation](https://docs.querymind.io)
- **Email Support**: support@querymind.io

## 🎯 Roadmap

- [ ] Advanced SQL optimization
- [ ] Query caching and execution statistics
- [ ] Multi-table join inference
- [ ] Data visualization support
- [ ] Custom prompt templates
- [ ] Team collaboration features
- [ ] API rate limiting per tier
- [ ] Advanced analytics dashboard
- [ ] GraphQL support
- [ ] Webhook integrations

## 🙏 Acknowledgments

- Built with [NestJS](https://nestjs.com/), [FastAPI](https://fastapi.tiangolo.com/), and [React](https://react.dev/)
- AI powered by [Ollama](https://ollama.ai/) and [HuggingFace](https://huggingface.co/)
- Inspired by the need for accessible database querying

---

**Made with ❤️ by the QueryMind Team**
