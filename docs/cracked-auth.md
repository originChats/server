# Cracked Authentication

OriginChats supports a self-contained authentication mode called "cracked" that allows users to register and authenticate without relying on Rotur.

## Configuration

Set the `auth_mode` in your `config.json`:

```json
{
  "auth_mode": "cracked-only",
  "cracked": {
    "allow_registration": true,
    "default_roles": ["user"]
  }
}
```

### Auth Modes

| Mode | Description |
|------|-------------|
| `rotur` | Only Rotur authentication allowed (default) |
| `cracked` | Both Rotur and cracked authentication allowed |
| `cracked-only` | Only cracked authentication allowed |

### Cracked Config Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `allow_registration` | bool | `true` | Allow new user registration |
| `default_roles` | array | `["user"]` | Roles assigned to new users |

## Client Implementation

### Detecting Auth Mode

The handshake message includes the `auth_mode` field:

```json
{
  "cmd": "handshake",
  "val": {
    "server": { ... },
    "auth_mode": "cracked-only",
    ...
  }
}
```

If `auth_mode` is `rotur`, use standard Rotur authentication flow.

If `auth_mode` is `cracked` or `cracked-only`, implement the cracked auth flow below.

### Registration

Send a `register` command:

```json
{
  "cmd": "register",
  "username": "alice",
  "password": "secret123"
}
```

**Response (success):**
```json
{
  "cmd": "auth_success",
  "val": "Authentication successful"
}
```

Followed by:
```json
{
  "cmd": "ready",
  "user": {
    "username": "USR:local_alice",
    "nickname": "alice",
    "roles": ["user"],
    "cracked": true,
    ...
  },
  "validator": "..."
}
```

**Response (error):**
```json
{
  "cmd": "auth_error",
  "val": "Username already taken"
}
```

### Login

Send a `login` command:

```json
{
  "cmd": "login",
  "username": "alice",
  "password": "secret123"
}
```

**Response (success):**
```json
{
  "cmd": "auth_success",
  "val": "Authentication successful"
}
```

Followed by the `ready` message.

**Response (error):**
```json
{
  "cmd": "auth_error",
  "val": "Invalid password"
}
```

### Profile Pictures

Cracked users can set a profile picture URL:

```json
{
  "cmd": "pfp_set",
  "url": "https://example.com/avatar.png"
}
```

**Response:**
```json
{
  "cmd": "pfp_set",
  "val": "https://example.com/avatar.png"
}
```

Get another user's profile picture:

```json
{
  "cmd": "pfp_get",
  "username": "alice"
}
```

**Response:**
```json
{
  "cmd": "pfp_get",
  "username": "alice",
  "val": "https://example.com/avatar.png"
}
```

## User Object

Cracked users have `cracked: true` in their user object:

```json
{
  "username": "USR:local_alice",
  "nickname": "alice",
  "roles": ["user"],
  "cracked": true,
  "pfp": "https://example.com/avatar.png",
  "status": {
    "status": "online",
    "text": ""
  }
}
```

**Note:** For cracked users:
- `username` includes the prefix (e.g., `USR:local_alice`)
- `nickname` is set to the raw username (e.g., `alice`) for display purposes
- Clients should display `nickname` if present, otherwise `username`
- Login/register uses the raw username without prefix

## User IDs

Internally, cracked users have IDs in the format `USR:local_{username}`.

For example, user `alice` has internal ID `USR:local_alice`.

## Username Rules

- 2-32 characters
- Alphanumeric, hyphens, and underscores only
- Case-insensitive (stored as lowercase)

## Password Rules

- Minimum 4 characters
- Hashed with bcrypt

## Example Client Flow

```
1. Connect WebSocket
2. Receive handshake with auth_mode
3. If cracked/cracked-only:
   a. Show login/register form
   b. Send register or login command
   c. Receive auth_success + ready
4. Connection established
```

## Security Notes

- Passwords are hashed with bcrypt before storage
- Cracked auth bypasses Rotur's account system entirely
- Consider rate limiting registration attempts
- Users are identified by username (case-insensitive)
