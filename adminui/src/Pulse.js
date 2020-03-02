import React, { useEffect, useState, useRef } from 'react';
import Sockette from 'sockette';
import { FaPlug } from 'react-icons/fa';
import './Pulse.css';

export default function Pulse({ onMessage }) {
  const [connected, setConnected] = useState(null);
  const [websocketErrored, setWebsocketErrored] = useState(false);

  let wssRef = useRef();
  useEffect(() => {
    let mounted = true;
    const wsUrl = process.env.REACT_APP_WS_URL || 'wss://admin.peterbe.com/ws';

    console.log(`Setting up WebSocket connection to ${wsUrl}`);
    wssRef.current = new Sockette(wsUrl, {
      timeout: 5e3,
      maxAttempts: 25,
      onopen: e => {
        if (mounted) {
          setConnected(true);
          setWebsocketErrored(false);
        }
      },
      onmessage: e => {
        let data;
        try {
          data = JSON.parse(e.data);
        } catch (ex) {
          console.warn('WebSocket message data is not JSON');
          data = e.data;
        }
        onMessage(data);
      },
      onreconnect: e => {
        console.log('Reconnecting WebSocket');
      },
      onmaximum: e => {
        console.log('Maximum attempts to reconnect. I give up.');
      },
      onclose: e => {
        if (mounted) setConnected(false);
      },
      onerror: e => {
        if (mounted) setWebsocketErrored(true);
      }
    });
    return () => {
      mounted = false;
      wssRef.current.close();
    };
  }, [onMessage]);

  return (
    <div
      id="pulse"
      onClick={() => {
        if (wssRef.current) {
          wssRef.current.reconnect();
        }
      }}
      title={
        websocketErrored
          ? `WebSocket Errored`
          : connected
          ? 'Connected!'
          : 'Not connected (click to attempt to reconnect)'
      }
    >
      <FaPlug
        size="1.5em"
        color={websocketErrored ? 'red' : connected ? 'green' : 'yellow'}
      />
    </div>
  );
}
