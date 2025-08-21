# Supabase Authentication Implementation

## Overview
This implementation adds Supabase authentication to the Git Service API, ensuring that all users must be authenticated before using the service.

## Environment Variables Required

Add these environment variables to your `.env` file:

```env
# Supabase Configuration
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key

# JWT Configuration
JWT_SECRET_KEY=your_jwt_secret_key
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24
```

## New Dependencies

The following packages have been added to `requirements.txt`:
- `supabase>=2.0.0` - Supabase Python client
- `python-jose[cryptography]>=3.3.0` - JWT token handling

## Authentication Endpoints

### POST `/auth/signup`
Create a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "full_name": "John Doe" // optional
}
```

**Response:**
```json
{
  "access_token": "jwt_token_here",
  "token_type": "bearer",
  "user": {
    "id": "user_id",
    "email": "user@example.com",
    "full_name": "John Doe"
  }
}
```

### POST `/auth/login`
Authenticate an existing user.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response:**
```json
{
  "access_token": "jwt_token_here",
  "token_type": "bearer",
  "user": {
    "id": "user_id",
    "email": "user@example.com",
    "user_metadata": {}
  }
}
```

### POST `/auth/logout`
Sign out the current user.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "message": "Successfully logged out"
}
```

### GET `/auth/me`
Get current user information.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "id": "user_id",
  "email": "user@example.com",
  "user_metadata": {},
  "created_at": "timestamp"
}
```

## Protected Endpoints

All the following endpoints now require authentication via Bearer token in the Authorization header:

- `POST /logs/raw`
- `POST /session/start`
- `POST /session/end`
- `GET /commits/recent`
- `POST /commits/search`
- `GET /commits/{commit_hash}`

## WebSocket Authentication

The WebSocket endpoint `/ws/execute` requires authentication via the first message:

**First Message (Authentication):**
```json
{
  "message_type": "authenticate",
  "token": "your_jwt_token_here"
}
```

**Authentication Success Response:**
```json
{
  "message_type": "auth_success",
  "user_id": "authenticated_user_id"
}
```

## Usage Example

1. **Sign up or log in:**
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password"
  }'
```

2. **Use the returned token for API calls:**
```bash
curl -X GET "http://localhost:8000/commits/recent" \
  -H "Authorization: Bearer <your_token_here>"
```

3. **For WebSocket connections:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/execute');
ws.onopen = () => {
  // First message must be authentication
  ws.send(JSON.stringify({
    message_type: 'authenticate',
    token: 'your_jwt_token_here'
  }));
};
```

## Security Features

- **JWT Token Validation:** All tokens are verified before granting access
- **User Session Isolation:** Users can only access their own sessions and data
- **Supabase Integration:** Leverages Supabase's secure authentication system
- **Bearer Token Authentication:** Standard OAuth2 Bearer token implementation
- **WebSocket Security:** Custom authentication flow for WebSocket connections

## Installation

1. Install the new dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your environment variables in a `.env` file

3. Configure your Supabase project with the appropriate settings

4. Start the application:
```bash
python app.py
```

The authentication system is now ready for production use and can be extended with additional features like role-based access control, rate limiting, and payment integration for the planned paywall.
