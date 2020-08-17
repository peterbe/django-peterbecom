import React, { useEffect } from 'react';
import { FaPlug } from 'react-icons/fa';
import { useWSS } from './WSSContext';
import './Pulse.css';

export default function Pulse({ onMessage }) {
  const { wss, connected, errored, register } = useWSS();
  useEffect(() => {
    register(onMessage);
  }, [register, onMessage]);

  return (
    <div
      id="pulse"
      onClick={() => {
        if (wss) {
          wss.reconnect();
        }
      }}
      title={
        errored
          ? `WebSocket Errored`
          : connected
          ? 'Connected!'
          : 'Not connected (click to attempt to reconnect)'
      }
    >
      <FaPlug
        size="1.5em"
        color={errored ? 'red' : connected ? 'green' : 'yellow'}
      />
    </div>
  );
}
