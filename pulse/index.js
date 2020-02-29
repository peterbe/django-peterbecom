const WebSocket = require('ws');
const redis = require('redis');

const REDIS_URL = process.env.REDIS_URL || null;
const WEBSOCKET_PORT = JSON.parse(process.env.WEBSOCKET_PORT || '8080');

const webSocketServer = new WebSocket.Server({ port: WEBSOCKET_PORT });
webSocketServer.on('connection', () => {
  console.log(`WebSocket server connection started on :${WEBSOCKET_PORT}`);
});
webSocketServer.on('open', () => {
  console.log(`WebSocket server open on :${WEBSOCKET_PORT}`);
});

function broadcastWebsocketMessage(msg) {
  if (!webSocketServer) {
    console.warn('No WebSocket server started');
    return;
  }
  if (typeof msg !== 'string') {
    msg = JSON.stringify(msg);
  }
  // let i = 0;
  webSocketServer.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      // i++;
      // console.log(`SENDING (${i})...`, msg);
      client.send(msg);
    }
  });
  // console.log(`Sent to ${i} open clients`);
}

const subscriber = redis.createClient(REDIS_URL);

subscriber.on('ready', () => {
  console.log('Redis ready');
});
subscriber.on('connect', () => {
  console.log('Redis stream is connected to the server');
});
subscriber.on('reconnecting', () => {
  console.log('Redis stream is reconnecting to the server');
});
subscriber.on('error', e => {
  console.log('Redis error', e);
});
subscriber.on('end', () => {
  console.log('Redis end');
});

subscriber.on('message', (channel, message) => {
  try {
    message = JSON.parse(message);
  } catch (ex) {
    // not JSON
  }
  console.log('INCOMING MESSAGE:', message);
  broadcastWebsocketMessage(message);
});
subscriber.subscribe('pulse');
