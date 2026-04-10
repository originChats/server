# Building a Client

How to build a client for OriginChats.

---

## Overview

A client connects to the server via WebSocket, authenticates the user, and sends/receives messages in real-time.

---

## Basic Structure

```
1. Connect to WebSocket
2. Handle handshake
3. Authenticate with Rotur
4. Load channels and messages
5. Listen for events
6. Send commands when user acts
```

---

## Step 1: Connect

```javascript
const ws = new WebSocket('ws://your-server:5613');

ws.onopen = () => {
  console.log('Connected');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  handleMessage(data);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

---

## Step 2: Handle Handshake

The server sends a handshake immediately after connecting:

```javascript
function handleMessage(data) {
  if (data.cmd === 'handshake') {
    // Save server info
    serverName = data.val.server.name;
    validatorKey = data.val.validator_key;
    
    // Now authenticate
    authenticate();
  }
}
```

---

## Step 3: Authenticate

### Get User Token

Redirect user to Rotur login:

```javascript
const authUrl = `https://rotur.dev/auth?return_to=${encodeURIComponent(window.location.href)}`;
window.location.href = authUrl;
```

After login, user returns with a token in the URL.

### Generate Validator

Exchange the token for a validator:

```javascript
async function generateValidator(token, validatorKey) {
  const url = `https://api.rotur.dev/generate_validator?auth=${token}&key=${validatorKey}`;
  const response = await fetch(url);
  const data = await response.json();
  return data.validator;
}
```

### Send Auth Command

```javascript
ws.send(JSON.stringify({
  cmd: 'auth',
  validator: validator
}));
```

### Handle Auth Response

```javascript
function handleMessage(data) {
  if (data.cmd === 'auth_success') {
    console.log('Logged in!');
  }
  
  if (data.cmd === 'ready') {
    currentUser = data.user;
    loadInitialData();
  }
  
  if (data.cmd === 'auth_error') {
    console.error('Auth failed:', data.val);
  }
}
```

---

## Step 4: Load Initial Data

```javascript
function loadInitialData() {
  // Get channels
  ws.send(JSON.stringify({ cmd: 'channels_get' }));
  
  // Get online users
  ws.send(JSON.stringify({ cmd: 'users_online' }));
}
```

---

## Step 5: Handle Events

Listen for server events and update your UI:

```javascript
function handleMessage(data) {
  switch (data.cmd) {
    // New message in channel
    case 'message_new':
      if (data.global) {
        displayMessage(data.channel, data.message);
      }
      break;
    
    // Message edited
    case 'message_edit':
      updateMessage(data.channel, data.id, data.content);
      break;
    
    // Message deleted
    case 'message_delete':
      removeMessage(data.channel, data.id);
      break;
    
    // User joined for first time
    case 'user_join':
      addUserToList(data.user);
      break;
    
    // User connected (any session)
    case 'user_connect':
      addUserToList(data.user);
      break;
    
    // User left server
    case 'user_disconnect':
      removeUserFromList(data.username);
      break;
    
    // User started typing
    case 'typing':
      showTypingIndicator(data.channel, data.user);
      break;
    
    // Reaction added
    case 'message_react_add':
      addReaction(data.channel, data.id, data.emoji, data.user);
      break;
    
    // Rate limited
    case 'rate_limit':
      showRateLimitWarning(data.length);
      break;
    
    // Error
    case 'error':
      showError(data.val);
      break;
  }
}
```

---

## Step 6: Send Commands

### Send a Message

```javascript
function sendMessage(channel, content) {
  ws.send(JSON.stringify({
    cmd: 'message_new',
    channel: channel,
    content: content
  }));
}
```

### Reply to a Message

```javascript
function replyToMessage(channel, content, replyToId) {
  ws.send(JSON.stringify({
    cmd: 'message_new',
    channel: channel,
    content: content,
    reply_to: replyToId,
    ping: true  // Notify the original author
  }));
}
```

### Edit a Message

```javascript
function editMessage(channel, messageId, newContent) {
  ws.send(JSON.stringify({
    cmd: 'message_edit',
    channel: channel,
    id: messageId,
    content: newContent
  }));
}
```

### Delete a Message

```javascript
function deleteMessage(channel, messageId) {
  ws.send(JSON.stringify({
    cmd: 'message_delete',
    channel: channel,
    id: messageId
  }));
}
```

### Add Reaction

```javascript
function addReaction(channel, messageId, emoji) {
  ws.send(JSON.stringify({
    cmd: 'message_react_add',
    channel: channel,
    id: messageId,
    emoji: emoji
  }));
}
```

### Send Typing Indicator

```javascript
function sendTyping(channel) {
  ws.send(JSON.stringify({
    cmd: 'typing',
    channel: channel
  }));
}
```

---

## Voice Channels

Voice uses WebRTC for peer-to-peer audio.

### Join a Voice Channel

```javascript
function joinVoice(channel) {
  // Generate WebRTC peer ID
  const peerId = generatePeerId();
  
  ws.send(JSON.stringify({
    cmd: 'voice_join',
    channel: channel,
    peer_id: peerId
  }));
}
```

### Handle Voice Events

```javascript
function handleMessage(data) {
  switch (data.cmd) {
    case 'voice_user_joined':
      // Connect to the new user via WebRTC
      connectToPeer(data.user.peer_id);
      break;
    
    case 'voice_user_left':
      // Disconnect from the user
      disconnectFromPeer(data.username);
      break;
    
    case 'voice_user_updated':
      // Update mute state in UI
      updateUserMuteState(data.user.username, data.user.muted);
      break;
  }
}
```

### WebRTC Setup

```javascript
// Create peer connection
const pc = new RTCPeerConnection({
  iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
});

// Add local audio stream
navigator.mediaDevices.getUserMedia({ audio: true })
  .then(stream => {
    pc.addTrack(stream.getAudioTracks()[0], stream);
  });

// Handle incoming stream
pc.ontrack = (event) => {
  const audio = new Audio();
  audio.srcObject = event.streams[0];
  audio.play();
};
```

---

## Threads (Forum Channels)

### Create a Thread

```javascript
function createThread(channel, title, content) {
  ws.send(JSON.stringify({
    cmd: 'thread_create',
    channel: channel,
    title: title,
    content: content
  }));
}
```

### Send Message to Thread

```javascript
function sendThreadMessage(threadId, content) {
  ws.send(JSON.stringify({
    cmd: 'message_new',
    thread_id: threadId,
    content: content
  }));
}
```

---

## Rate Limiting

Handle rate limits gracefully:

```javascript
let rateLimitedUntil = 0;

function handleMessage(data) {
  if (data.cmd === 'rate_limit') {
    rateLimitedUntil = Date.now() + data.length;
    showWarning(`Slow down! Wait ${Math.ceil(data.length / 1000)} seconds.`);
  }
}

function sendMessage(channel, content) {
  if (Date.now() < rateLimitedUntil) {
    showWarning('You are rate limited. Please wait.');
    return;
  }
  
  ws.send(JSON.stringify({
    cmd: 'message_new',
    channel: channel,
    content: content
  }));
}
```

---

## Complete Example

Minimal working client:

```html
<!DOCTYPE html>
<html>
<head>
  <title>OriginChats Client</title>
</head>
<body>
  <div id="messages"></div>
  <input id="input" type="text" placeholder="Type a message...">
  <button onclick="send()">Send</button>
  
  <script>
    const ws = new WebSocket('ws://localhost:5613');
    let currentChannel = 'general';
    let validatorKey;
    
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      
      if (data.cmd === 'handshake') {
        validatorKey = data.val.validator_key;
        // In real app, get token from Rotur login first
        // Then generate validator and send auth
      }
      
      if (data.cmd === 'ready') {
        ws.send(JSON.stringify({ cmd: 'channels_get' }));
      }
      
      if (data.cmd === 'message_new') {
        const div = document.createElement('div');
        div.textContent = `${data.message.user}: ${data.message.content}`;
        document.getElementById('messages').appendChild(div);
      }
    };
    
    function send() {
      const input = document.getElementById('input');
      ws.send(JSON.stringify({
        cmd: 'message_new',
        channel: currentChannel,
        content: input.value
      }));
      input.value = '';
    }
  </script>
</body>
</html>
```

---

## Unreads Tracking

Server-side unread tracking is available for channels and threads.

### Get All Unreads

```javascript
ws.send(JSON.stringify({ cmd: 'unreads_get' }));

// Response:
// {
//   cmd: 'unreads_get',
//   unreads: {
//     'general': { last_read: 'msg_123', unread_count: 5, total_messages: 100 },
//     'random': { last_read: null, unread_count: 50, total_messages: 50 }
//   }
// }
```

### Mark as Read (Explicit Ack)

```javascript
// Mark channel as read (up to latest message)
ws.send(JSON.stringify({ cmd: 'unreads_ack', channel: 'general' }));

// Mark channel as read up to specific message
ws.send(JSON.stringify({ cmd: 'unreads_ack', channel: 'general', message_id: 'msg_456' }));

// Mark thread as read
ws.send(JSON.stringify({ cmd: 'unreads_ack', thread_id: 'thread_123' }));
```

### Get Unread Count for Single Channel/Thread

```javascript
ws.send(JSON.stringify({ cmd: 'unreads_count', channel: 'general' }));

// Response:
// {
//   cmd: 'unreads_count',
//   channel: 'general',
//   unread_count: 5,
//   last_read: 'msg_123',
//   total_messages: 100
// }
```

### Auto-Ack on Fetch

When you call `messages_get`, the server automatically marks the channel/thread as read up to the latest message. This is synced across all your connections.

### Listen for Unread Updates

```javascript
function handleMessage(data) {
  if (data.cmd === 'unreads_update') {
    // Another connection updated read state
    console.log('Read state updated:', data.channel || data.thread_id, data.last_read);
  }
}
```

---

## Best Practices

1. **Reconnect on disconnect** - Handle WebSocket close events
2. **Queue messages when disconnected** - Send when reconnected
3. **Show connection status** - Let users know if they're connected
4. **Handle errors gracefully** - Show user-friendly messages
5. **Debounce typing indicators** - Don't send too frequently
6. **Cache messages locally** - Reduce load on server

---

## Existing Clients

See [clients.md](../clients.md) for existing clients you can use or learn from.

---

## Next Steps

- [Command Reference](commands/) - All available commands
- [Data Structures](reference.md) - Message, user, channel formats
- [Getting Started](getting-started.md) - Detailed connection flow
