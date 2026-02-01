# Remote Access System - API Documentation

## Base URL

```
https://your-domain.com/api
```

## Authentication

All authenticated endpoints require a Bearer token in the Authorization header:

```
Authorization: Bearer YOUR_JWT_TOKEN
```

Obtain a token by calling the `/auth/login` endpoint.

## Endpoints

### Authentication

#### POST /auth/login

Authenticate a user and receive a JWT token.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "full_name": "John Doe",
    "role": "tech"
  }
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid credentials

---

### User Management

#### POST /users

Create a new IT member. **Admin only**.

**Headers:**
```
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "newuser@example.com",
  "password": "securepass123",
  "full_name": "Jane Smith",
  "role": "tech",
  "max_sessions": 10
}
```

**Response (200 OK):**
```json
{
  "id": 2,
  "email": "newuser@example.com",
  "full_name": "Jane Smith",
  "role": "tech",
  "max_sessions": 10,
  "is_active": true,
  "created_at": "2026-01-31T10:30:00"
}
```

**Error Responses:**
- `400 Bad Request`: User already exists or validation error
- `403 Forbidden`: Admin access required

---

#### GET /users

List all users. **Admin only**.

**Headers:**
```
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "email": "admin@localhost",
    "full_name": "System Administrator",
    "role": "admin",
    "max_sessions": 50,
    "is_active": true,
    "created_at": "2026-01-01T00:00:00"
  },
  {
    "id": 2,
    "email": "tech@example.com",
    "full_name": "John Tech",
    "role": "tech",
    "max_sessions": 10,
    "is_active": true,
    "created_at": "2026-01-15T14:20:00"
  }
]
```

---

### SMTP Configuration

#### POST /smtp/config

Configure SMTP settings for email notifications. **Admin only**.

**Headers:**
```
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "smtp_host": "smtp.office365.com",
  "smtp_port": 587,
  "security_type": "TLS",
  "username": "noreply@company.com",
  "password": "app_password_here",
  "from_email": "noreply@company.com",
  "require_auth": true
}
```

**Response (200 OK):**
```json
{
  "message": "SMTP configured successfully"
}
```

**Field Descriptions:**
- `smtp_host`: SMTP server hostname (e.g., smtp.gmail.com, smtp.office365.com)
- `smtp_port`: SMTP port number (587 for TLS, 465 for SSL, 25 for none)
- `security_type`: One of "TLS", "SSL", or "NONE"
- `username`: SMTP authentication username
- `password`: SMTP authentication password (app password for Gmail/O365)
- `from_email`: Email address to send from
- `require_auth`: Whether SMTP authentication is required (boolean)

**Error Responses:**
- `403 Forbidden`: Admin access required
- `400 Bad Request`: Invalid configuration

---

#### GET /smtp/config

Get current SMTP configuration (password hidden). **Admin only**.

**Headers:**
```
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
  "configured": true,
  "smtp_host": "smtp.office365.com",
  "smtp_port": 587,
  "security_type": "TLS",
  "username": "noreply@company.com",
  "from_email": "noreply@company.com",
  "require_auth": true
}
```

**Response if not configured (200 OK):**
```json
{
  "configured": false
}
```

---

### Session Management

#### POST /sessions

Create a new remote access session.

**Headers:**
```
Authorization: Bearer {token}
Content-Type: application/json
```

**Request Body:**
```json
{
  "customer_name": "John Customer",
  "customer_email": "customer@example.com"
}
```

**Note:** Both fields are optional. If `customer_email` is provided, the session code will be emailed automatically.

**Response (200 OK):**
```json
{
  "id": 123,
  "session_code": "482916573",
  "tech_user_id": 1,
  "customer_name": "John Customer",
  "customer_email": "customer@example.com",
  "status": "pending",
  "udp_port": 50001,
  "created_at": "2026-01-31T15:45:00"
}
```

**Error Responses:**
- `429 Too Many Requests`: Maximum concurrent sessions reached
- `500 Internal Server Error`: Failed to allocate UDP port

**Session Status Values:**
- `pending`: Session created, waiting for client connection
- `active`: Client connected and streaming
- `disconnected`: Client disconnected
- `closed`: Session manually closed by IT member

---

#### GET /sessions

List sessions for current user (or all sessions for admins).

**Headers:**
```
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
[
  {
    "id": 123,
    "session_code": "482916573",
    "tech_user_id": 1,
    "customer_name": "John Customer",
    "customer_email": "customer@example.com",
    "status": "active",
    "udp_port": 50001,
    "created_at": "2026-01-31T15:45:00"
  },
  {
    "id": 122,
    "session_code": "391847562",
    "tech_user_id": 1,
    "customer_name": null,
    "customer_email": null,
    "status": "closed",
    "udp_port": 50002,
    "created_at": "2026-01-31T14:30:00"
  }
]
```

**Note:** Returns last 100 sessions, ordered by creation date (newest first).

---

#### DELETE /sessions/{session_id}

Close/terminate a session.

**Headers:**
```
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
  "message": "Session closed successfully"
}
```

**Error Responses:**
- `404 Not Found`: Session does not exist
- `403 Forbidden`: Access denied (can only close own sessions unless admin)

---

#### GET /sessions/{session_code}/info

Get session information by session code. **No authentication required** (used by client).

**Response (200 OK):**
```json
{
  "session_code": "482916573",
  "udp_port": 50001,
  "status": "pending"
}
```

**Error Responses:**
- `404 Not Found`: Session not found
- `410 Gone`: Session has been closed

---

### WebSocket Endpoints

#### WS /ws/session/{session_code}

WebSocket connection for session signaling and control.

**Connection URL:**
```
ws://your-domain.com/ws/session/482916573
```

**Message Format:**

Client → Server:
```json
{
  "type": "ping"
}
```

Server → Client:
```json
{
  "type": "pong"
}
```

Disconnect:
```json
{
  "type": "disconnect"
}
```

**Connection Lifecycle:**
1. Client connects with session code
2. Server validates session and updates status to "active"
3. Bidirectional messages for control and signaling
4. On disconnect, server updates session status to "disconnected"

---

## UDP Protocol

### Port Allocation

Sessions are allocated UDP ports in the range **50000-60000**.

### Packet Structure

#### Frame Data Packet (Type 1)

```
[1 byte]  Packet Type = 1
[8 bytes] Frame ID (timestamp)
[4 bytes] Chunk Index
[4 bytes] Total Chunks
[4 bytes] Total Image Size
[N bytes] Image Data (JPEG chunk)
```

#### Mouse Event Packet (Type 2)

```
[1 byte]  Packet Type = 2
[4 bytes] X Position
[4 bytes] Y Position
[1 byte]  Button (1=Left, 2=Right, 3=Middle)
[1 byte]  Button State (1=Down, 0=Up)
```

#### Keyboard Event Packet (Type 3)

```
[1 byte]  Packet Type = 3
[2 bytes] Virtual Key Code
[1 byte]  Key State (1=Down, 0=Up)
```

#### Control Message Packet (Type 4)

```
[1 byte]  Packet Type = 4
[N bytes] JSON Message (UTF-8)
```

### Frame Transmission

1. Client captures screen at 15 FPS
2. Image compressed to JPEG (quality 60%)
3. Image split into ~60KB chunks
4. Each chunk sent as separate UDP packet
5. IT member's viewer reassembles chunks by Frame ID

---

## Error Codes

### HTTP Status Codes

- `200 OK`: Request successful
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required or token invalid
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `410 Gone`: Resource no longer available
- `429 Too Many Requests`: Rate limit or session limit exceeded
- `500 Internal Server Error`: Server error

### Common Error Response Format

```json
{
  "detail": "Error message here"
}
```

---

## Rate Limiting

- **API Endpoints**: No built-in rate limiting (configure in Nginx)
- **Sessions per User**: Configurable per user (default: 10 concurrent)
- **UDP Bandwidth**: Limited by network and CPU capacity

---

## Security Considerations

### JWT Tokens
- Tokens expire after 24 hours
- Store securely on client side
- Include in Authorization header for all protected endpoints

### HTTPS
- All API communication should use HTTPS in production
- WebSocket connections should use WSS (secure WebSocket)

### SMTP Passwords
- Never returned in API responses
- Stored in database (consider encryption)
- Use app-specific passwords for Gmail/Microsoft 365

### UDP Security
- No built-in encryption (implement TLS/DTLS if needed)
- Session codes are 9 digits (1 billion combinations)
- Sessions expire and can be closed remotely

---

## Code Examples

### Python - Create Session

```python
import requests

API_URL = "https://your-domain.com/api"

# Login
response = requests.post(f"{API_URL}/auth/login", json={
    "email": "tech@example.com",
    "password": "password123"
})
token = response.json()["access_token"]

# Create session
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(f"{API_URL}/sessions", headers=headers, json={
    "customer_name": "John Doe",
    "customer_email": "john@example.com"
})

session = response.json()
print(f"Session Code: {session['session_code']}")
print(f"UDP Port: {session['udp_port']}")
```

### JavaScript - List Sessions

```javascript
const API_URL = 'https://your-domain.com/api';

async function listSessions(token) {
  const response = await fetch(`${API_URL}/sessions`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  const sessions = await response.json();
  return sessions;
}

// Usage
const token = 'your-jwt-token';
const sessions = await listSessions(token);
console.log(sessions);
```

### C# - Connect to Session

```csharp
using System.Net.Http;
using Newtonsoft.Json;

public async Task<SessionInfo> GetSessionInfo(string sessionCode)
{
    using (HttpClient client = new HttpClient())
    {
        var response = await client.GetAsync(
            $"https://your-domain.com/api/sessions/{sessionCode}/info"
        );
        
        response.EnsureSuccessStatusCode();
        var json = await response.Content.ReadAsStringAsync();
        return JsonConvert.DeserializeObject<SessionInfo>(json);
    }
}
```

---

## Versioning

Current API Version: **v1.0**

The API follows semantic versioning. Breaking changes will result in a new major version.

---

## Support

For API support or to report bugs:
- GitHub Issues: https://github.com/yourcompany/remote-access/issues
- Email: api-support@yourcompany.com
- Documentation: https://docs.yourcompany.com/api

---

**Last Updated**: January 31, 2026
