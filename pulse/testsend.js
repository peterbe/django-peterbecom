const redis = require('redis');

const REDIS_URL = process.env.REDIS_URL || null;

const publisher = redis.createClient(REDIS_URL);

publisher.on('ready', () => {
  console.log('Redis ready');
});
publisher.on('connect', () => {
  console.log('Redis stream is connected to the server');
});
publisher.on('reconnecting', () => {
  console.log('Redis stream is reconnecting to the server');
});
publisher.on('error', e => {
  console.log('Redis error', e);
});
publisher.on('end', () => {
  console.log('Redis end');
});

const messages = process.argv.slice(2).map(m => {
  try {
    return JSON.stringify(JSON.parse(m));
  } catch (ex) {
    return m;
  }
});

messages.forEach((message, i) => {
  publisher.publish('pulse', message, () => {
    console.log('Message sent!');
    if (i === messages.length - 1) process.exit(0);
  });
});
