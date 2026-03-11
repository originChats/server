# Roles Structure

Roles define user capabilities and permissions in OriginChats. Each user can have one or more roles, such as `user`, `admin`, `moderator`, or `owner`.

Example role object:

```json
{
  "name": "moderator",
  "color": "#00aaff",
  "description": "Moderators can manage messages and users.",
  "hoisted": true,
  "permissions": {
    "mention_roles": true
  }
}
```

- `name`: Role name (string).
- `color`: Hex color code for UI display.
- `description`: Description of the role.
- `hoisted`: Boolean. If `true`, the role is displayed separately/prominently in the user list.
- `permissions`: Object of server-wide (non-channel-specific) permissions for this role.

## Role Permissions

Unlike [channel permissions](permissions.md) which control per-channel actions, role permissions are server-wide capabilities stored directly on the role.

### `mention_roles`

Controls who can use `@&rolename` to mention this role in messages.

- `true` — anyone can mention this role (default if omitted)
- `false` — nobody can mention this role (except `owner`)
- `"rolename"` — only users with that specific role can mention it
- `["role1", "role2"]` — only users with one of those roles can mention it

The `owner` role always bypasses this check.

Example: a `cuties` role that only admins and moderators can ping:

```json
{
  "mention_roles": ["admin", "moderator"]
}
```

## Managing Role Permissions

Use the `role_permissions_set` command (owner only) to update a role's permissions object wholesale, or include a `permissions` field when calling `role_create` / `role_update`.

Use `role_permissions_get` to read the current permissions for any role (any authenticated user).

Roles are also used in [channel permissions](permissions.md) to control access to actions such as `view`, `send`, `delete`, `pin`, `react`, and more.
