# Configuration: config.json

This file contains the main configuration for the OriginChats server. Below is a description of each section and field:

---

## limits

- **post_content**: *(int)*
  - Maximum number of characters allowed in a single message/post.
- **search_results**: *(int)*
  - Maximum number of results returned by `messages_search`.

## uploads

- **emoji_allowed_file_types**: *(list of str)*
  - Allowed file extensions for custom emoji uploads.

## rate_limiting

- **enabled**: *(bool)*
  - Whether rate limiting is enabled for message sending.
- **messages_per_minute**: *(int)*
  - Maximum number of messages a user can send per minute.
- **burst_limit**: *(int)*
  - Maximum number of messages allowed in a short burst before cooldown is enforced.
- **cooldown_seconds**: *(int)*
  - Number of seconds a user must wait after hitting the burst limit.

## DB

- **channels**: *(str)*
  - Path to the channels database file.
- **users**: *(object)*
  - **file**: *(str)*
    - Path to the users database file.
  - **default**: *(object)*
    - **roles**: *(list of str)*
      - Default roles assigned to new users.

## websocket

- **host**: *(str)*
  - Host address for the websocket server.
- **port**: *(int)*
  - Port number for the websocket server.

## service

- **name**: *(str)*
  - Name of the service.
- **version**: *(str)*
  - Version of the service.

## server

- **name**: *(str)*
  - Name of the server instance.
- **owner**: *(object)*
  - **name**: *(str)*
    - Name of the server owner.
- **icon**: *(str)*
  - URL to the server icon image, or the filename of a file already stored in `db/serverAssets`; it will be exposed as `/server-assets/icon`.
- **banner**: *(str)*
  - URL to the server banner image, or the filename of a file already stored in `db/serverAssets`; it will be exposed as `/server-assets/banner`.
- **url**: *(str)*
  - Public base URL of the server, used to build hosted links for local server icon and banner files.

---

## Adding New Config

When adding a new config value, follow these 3 steps:

1. Add the default value in `config_builder.py` under `DEFAULT_CONFIG`.
2. If it should be set during setup, add a prompt in `setup.py` and add the parsed value to the overrides passed into `build_config(...)`.
3. Read it in runtime code through `get_config_value(...)` from `config_store.py`, or through the local `_config_value(...)` helper in handlers when `server_data["config"]` is already available.

Example:

- Add `limits.search_results` in `config_builder.py`.
- Prompt for it in `setup.py`.
- Read it with `get_config_value("limits", "search_results", default=30)`.

---

**Location:** `config.json`

This file should be kept secure, especially fields containing API keys or sensitive URLs.
