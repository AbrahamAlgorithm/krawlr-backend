# Krawlr Backend

A FastAPI-based authentication backend using Google Cloud Firestore for user management.

## Features

- ✅ User registration with email validation
- ✅ User authentication with JWT tokens
- ✅ Password hashing using bcrypt
- ✅ Firestore integration for data persistence
- ✅ Environment-based configuration
- ✅ Input validation with Pydantic

## Tech Stack

- **Framework**: FastAPI 0.121.2
- **Database**: Google Cloud Firestore
- **Authentication**: JWT (python-jose)
- **Password Hashing**: bcrypt (passlib)
- **Validation**: Pydantic
- **Server**: Uvicorn

## Project Structure

```
krawlr-backend/
├── app/
│   ├── api/
│   │   └── routes.py          # API endpoints
│   ├── core/
│   │   ├── auth.py            # JWT token generation
│   │   ├── config.py          # Configuration loader
│   │   └── database.py        # Firestore client initialization
│   ├── schemas/
│   │   └── user.py            # Pydantic models
│   ├── services/
│   │   └── user_service.py    # User business logic
│   ├── utils/
│   │   └── security.py        # Password hashing utilities
│   └── main.py                # FastAPI app entry point
├── .env                        # Environment variables
├── .gitignore
├── requirements.txt
└── README.md
```

## Prerequisites

- Python 3.9+
- Google Cloud Project with Firestore enabled
- Service account JSON file for Firestore

## Setup Instructions

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd krawlr-backend
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

Create or update `.env` file in the project root:

```env
GOOGLE_APPLICATION_CREDENTIALS=serviceAccount.json
SECRET_KEY=your_super_secret_jwt_key_here_change_in_production
```

**Important**: 
- Replace `your_super_secret_jwt_key_here_change_in_production` with a strong random secret
- Generate a secure key: `openssl rand -hex 32`

### 5. Set up Google Cloud Firestore

1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable Firestore API
3. Create a service account with Firestore permissions
4. Download the service account JSON file
5. Save it as `serviceAccount.json` in the project root
6. Ensure `GOOGLE_APPLICATION_CREDENTIALS` in `.env` points to this file

### 6. Run the application

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Health Check

```bash
GET /
```

**Response:**
```json
{
  "Status": "App is running"
}
```

### Register User

```bash
POST /auth/register
Content-Type: application/json

{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "securepassword123"
}
```

**Response:**
```json
{
  "message": "User created successfully",
  "user": {
    "id": "john@example.com",
    "name": "John Doe",
    "email": "john@example.com"
  }
}
```

### Login User

```bash
POST /auth/login
Content-Type: application/json

{
  "email": "john@example.com",
  "password": "securepassword123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

## Testing with curl

### Register a new user

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Smith",
    "email": "jane@example.com",
    "password": "mypassword123"
  }'
```

### Login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "jane@example.com",
    "password": "mypassword123"
  }'
```

## Interactive API Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Development

### Running in development mode

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Code structure guidelines

- **Routes** (`app/api/routes.py`): HTTP endpoint definitions
- **Services** (`app/services/`): Business logic layer
- **Schemas** (`app/schemas/`): Pydantic models for validation
- **Core** (`app/core/`): Configuration, database, authentication
- **Utils** (`app/utils/`): Utility functions

## Security Notes

⚠️ **Important Security Practices**:

1. **Never commit sensitive files**:
   - `serviceAccount.json` - contains GCP credentials
   - `.env` - contains secret keys
   
2. **Use strong secrets**:
   - Generate SECRET_KEY with: `openssl rand -hex 32`
   - Change default keys before production
   
3. **Firestore Security Rules**:
   - Configure proper Firestore security rules in production
   - Don't rely solely on backend validation

4. **HTTPS in Production**:
   - Always use HTTPS in production
   - Consider using a reverse proxy (nginx, Traefik)

## Troubleshooting

### Pylance "Import could not be resolved" error

1. Ensure virtual environment is created and activated
2. In VS Code: Command Palette → "Python: Select Interpreter" → Choose `.venv/bin/python`
3. Restart language server: Command Palette → "Python: Restart Language Server"

### Firestore connection issues

1. Verify `serviceAccount.json` exists and path is correct in `.env`
2. Check service account has Firestore permissions
3. Ensure Firestore API is enabled in Google Cloud Console

### Module import errors

```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

## Future Enhancements

- [ ] Add unit tests with pytest
- [ ] Implement refresh tokens
- [ ] Add email verification
- [ ] Rate limiting
- [ ] Logging and monitoring
- [ ] Password reset functionality
- [ ] User profile endpoints
- [ ] Docker containerization

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]
