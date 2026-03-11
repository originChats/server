# Server Events: user_join, user_connect, and user_leave

## user_join

Broadcast to all connected clients when a **new user joins the server for the first time** (i.e., when they're added to the user list).

### Event Data

```json
{
  "cmd": "user_join",
  "user": {
    "username": "john_doe",
    "roles": ["user"],
    "color": null
  }
}
```

### Fields

- `username`: The username of the new user who joined
- `roles`: Array of role names the user has (typically just `["user"]` initially)
- `color`: Color of the user's highest priority role (usually `null` for new users)

### Behavior

- Broadcast to all authenticated connected clients
- Sent **only once** per user - when they first join the server
- Triggered when a new user is created and added to the user list
- Not sent when an existing user reconnects

### Handling

Clients should:
1. Listen for `user_join` events
2. Add the user to local user database/server member list
3. Show a notification that a new member joined the server
4. Update UI to reflect the new member
5. Optionally send a welcome message

### Example

```javascript
websocket.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.cmd === 'user_join') {
    const user = data.user;
    addUserToServer(user);
    console.log(`${user.username} joined the server for the first time!`);

    // Show celebration notification
    showNotification(`🎉 ${user.username} joined the server!`, 'success');

    // Add to members list
    addToServerMembers(user);
  }
};

function addUserToServer(user) {
  // Add to the server's members list (persists across sessions)
  serverMembers.set(user.username, {
    username: user.username,
    roles: user.roles,
    color: user.color,
    joinedAt: Date.now()
  });

  // Update UI
  updateMemberCount();
  renderMemberList();
}
```

## user_connect

Broadcast to all connected clients when **any user connects to the server** (every WebSocket connection).

### Event Data

```json
{
  "cmd": "user_connect",
  "user": {
    "username": "john_doe",
    "roles": ["user", "moderator"],
    "color": "#FF5733"
  }
}
```

### Fields

- `username`: The username of the user who connected
- `roles`: Array of role names the user has
- `color`: Color of the user's highest priority role (if any)

### Behavior

- Broadcast to all authenticated connected clients
- Sent **every time** a user connects for every connection
- Triggered after successful authentication
- Includes user's current roles and color
- Sent for both new users and returning users

### Handling

Clients should:
1. Listen for `user_connect` events
2. Add the user to their **online users** list
3. Update UI to show the user is online
4. Update online user count
5. Show a subtle notification (optional)

### Difference from user_join

- `user_join`: Sent **once** when user first joins (persists in member list)
- `user_connect`: Sent **every time** user connects (online status)

### Example

```javascript
let onlineUsers = new Map();

websocket.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.cmd === 'user_connect') {
    const user = data.user;
    addOnlineUser(user);
    console.log(`${user.username} is now online`);

    // Show online indicator
    showOnlineStatus(user.username);
  }
};

function addOnlineUser(user) {
  // Add to local online users list (transient)
  onlineUsers.set(user.username, {
    username: user.username,
    roles: user.roles,
    color: user.color
  });

  // Update UI
  updateOnlineUsersCount();
  renderOnlineUsersList();
}
```

## user_leave

Broadcast to all connected clients when a user disconnects from the server.

### Event Data

```json
{
  "cmd": "user_leave",
  "username": "john_doe"
}
```

### Fields

- `username`: The username of the user who left

### Behavior

- Broadcast to all authenticated connected clients
- Sent when a WebSocket connection is closed (for any reason)
- Indicates the user is no longer connected
- Does NOT remove user from server member list, only from online users

### Handling

Clients should:
1. Listen for `user_leave` events
2. Remove the user from their **online users** list
3. Update UI to reflect the user going offline
4. Update online user count
5. Cancel any pending notifications for that user

### Example

```javascript
websocket.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.cmd === 'user_leave') {
    const username = data.username;
    removeOnlineUser(username);
    console.log(`${username} is now offline`);

    // Show offline indicator
    showOfflineStatus(username);
  }
};

function removeOnlineUser(username) {
  // Remove from local online users list only
  onlineUsers.delete(username);

  // Update UI
  updateOnlineUsersCount();
  renderOnlineUsersList();
}
```

## Event Lifecycle

### First-Time User

```
[User creates account & connects]
        ↓
[Server creates user record]
        ↓
[sends userJoin = true to auth handler]
        ↓
[Broadcasts user_join]
        ↓
[All clients: Add to server members + notify]
        ↓
[Broadcasts user_connect]
        ↓
[All clients: Mark as online]
```

### Returning User (Reconnect)

```
[Existing user connects]
        ↓
[userJoin = false (already in system)]
        ↓
[No user_join broadcast]
        ↓
[Broadcasts user_connect]
        ↓
[All clients: Mark as online (already in member list)]
        ↓
[Disconnects]
        ↓
[Broadcasts user_leave]
        ↓
[All clients: Mark as offline (still in member list)]
```

## User State Example

```javascript
// Two separate data structures:

// Server Members (Persistent - from user_join events)
serverMembers = {
  "alice":  { username: "alice", roles: ["admin"],    joinedAt: 1234567890 },
  "bob":    { username: "bob",   roles: ["user"],     joinedAt: 1234567900 },
  "charlie": { username: "charlie",roles: ["user"],  joinedAt: 1234567910 }
};

// Online Users (Transient - from user_connect/user_leave events)
onlineUsers = {
  "alice": { username: "alice", roles: ["admin"], online: true },
  "bob":   { username: "bob",   roles: ["user"],  online: false }, // Left
  "charlie": { username: "charlie", roles: ["user"], online: true }
};
```

## Best Practices for Client Handling

1. **Separate data structures**: Maintains separate lists for:
   - Server members (from `user_join` events)
   - Online users (from `user_connect`/`user_leave` events)

2. **Handle duplicate events**: User can connect multiple times, deduplicate online list

3. **Sync on connect**: Fetch both members list (via `users_list`) and online list (via `users_online`) when connecting

4. **Update UI appropriately**:
   - `user_join`: Show prominent welcome/announcement
   - `user_connect`: Show subtle online indicator
   - `user_leave`: Update online status only

5. **Persist user_join data**: Store member data locally to recognize returning users

## Implementation Details

### user_join
- **Triggered in**: `handlers/auth.py` in `handle_authentication()`
- **Condition**: Only when `is_new_user` is `true` (user record didn't exist)
- **Broadcast to**: All authenticated connected clients
- **Timing**: After user record is created, before authentication completes
- **Purpose**: Signal that a new member has joined the server community

### user_connect
- **Triggered in**: `handlers/auth.py` in `handle_authentication()`
- **Condition**: Every successful authentication (returns true on success)
- **Broadcast to**: All authenticated connected clients
- **Timing**: After `user_join` (if new), just before authentication completes
- **Purpose**: Signal that a user is now online (for returning users)

### user_leave
- **Triggered in**: `server.py` in `handle_client()` finally block
- **Condition**: When WebSocket connection is closed (any reason)
- **Broadcast to**: All authenticated connected clients
- **Timing**: Connection cleanup (before removing from connected_clients)
- **Purpose**: Signal that a user has gone offline
- Also removes slash commands registered by that user's connection

## Security Considerations

- All events only include public user information (not private data)
- Client receives these events automatically upon authentication
- No additional authentication needed to receive these events
- User information is limited to: username, roles, and role color (no IDs or sensitive data)

## Related

- [users_online](../commands/users_online.md) - Request the full list of online users
- [users_list](../commands/users_list.md) - Request the full list of server members
- Welcome Plugin - Automatically sends welcome messages to new users

See implementation:
- `handlers/auth.py` (search for `Broadcast user_join` and `Broadcast user_connect`)
- `server.py` (search for `user_leave`)

