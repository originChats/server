# Command: users_list

**Request:**
```json
{"cmd": "users_list"}
```

**Response:**
- On success:
```json
{
  "cmd": "users_list",
  "users": [
    {
      "username": "example_user",
      "nickname": "Display Name",
      "color": "#hexcode",
      "status": {
        "status": "online",
        "text": "Working on something cool"
      },
      "roles": ["role1", "role2"],
      "cracked": false,
      "pfp": "https://example.com/avatar.png"
    }
  ]
}
```
- On error: see [common errors](errors.md).

- Typescript:
```ts
interface User {
  username: string;
  nickname?: string;
  roles?: string[];
  color?: string | null;
  status?: {
    status: "online" | "idle" | "dnd" | "offline";
    text?: string;
  };
  cracked: boolean;
  pfp?: string | null;
}

interface UsersList {
  cmd: "users_list";
  users: User[];
}
```

**User Object Fields:**
- `username` - The user's username
- `nickname` - The user's display nickname (optional, may not be present)
- `color` - The user's top role colour
- `status` - Object containing `status` (online/idle/dnd/invisible) and `text` (custom message)
- `roles` - Array of role names assigned to the user
- `cracked` - Boolean indicating if the account uses cracked (local) authentication
- `pfp` - Profile picture URL (optional, may be null for Rotur users or if not set for cracked users)

**Notes:**
- User must be authenticated.

See implementation: [`handlers/message.py`](../handlers/message.py) (search for `case "users_list":`).
