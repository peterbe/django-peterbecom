import React, {
  useContext,
  createContext,
  useEffect,
  useState,
  useRef,
} from 'react';
import Sockette from 'sockette';

const WSSContext = createContext(null);

class Callbacks {
  constructor() {
    this.functions = [];
    this.register = this.register.bind(this);
  }
  send(msg) {
    this.functions.forEach(({ func, filter }) => {
      if (!filter || msg[filter]) {
        func(msg);
      }
    });
  }
  register(func, filter) {
    if (filter && filter instanceof String) {
      filter = [filter];
    }
    this.functions.push({ func, filter });
  }
}

export function WSSProvider({ children }) {
  const [connected, setConnected] = useState(null);
  const [websocketErrored, setWebsocketErrored] = useState(false);

  const cbs = new Callbacks();
  const callbacks = useRef(cbs);

  let wssRef = useRef();
  useEffect(() => {
    console.log('WSSProvider mounted');
    let mounted = true;
    const wsUrl = process.env.REACT_APP_WS_URL || 'wss://admin.peterbe.com/ws';

    console.log(`Setting up WebSocket connection to ${wsUrl}`);
    wssRef.current = new Sockette(wsUrl, {
      timeout: 5e3,
      maxAttempts: 25,
      onopen: (e) => {
        console.log('WebSocket connected!');
        if (mounted) {
          setConnected(true);
          setWebsocketErrored(false);
        }
      },
      onmessage: (e) => {
        let data;
        try {
          data = JSON.parse(e.data);
        } catch (ex) {
          console.warn('WebSocket message data is not JSON');
          data = e.data;
        }
        callbacks.current.send(data);
      },
      onreconnect: (e) => {
        console.log('Reconnecting WebSocket');
      },
      onmaximum: (e) => {
        console.log('Maximum attempts to reconnect. I give up.');
      },
      onclose: (e) => {
        if (mounted) setConnected(false);
      },
      onerror: (e) => {
        if (mounted) setWebsocketErrored(true);
      },
    });

    return () => {
      mounted = false;
      wssRef.current.close();
    };
  }, []);

  var returnThese = {
    register: callbacks.current.register,
    wss: wssRef.current,
    connected,
    errored: websocketErrored,
  };
  return (
    <WSSContext.Provider value={returnThese}>{children}</WSSContext.Provider>
  );
}

export function useWSS() {
  return useContext(WSSContext);
}
