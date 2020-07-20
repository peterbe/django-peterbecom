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
    this.functions.forEach((f) => f(msg));
  }
  register(f) {
    this.functions.push(f);
  }
}

// const cbs = new Callbacks();

export function WSSProvider({ children }) {
  //   const [wss, setWss] = useState(null);
  const [connected, setConnected] = useState(null);
  const [websocketErrored, setWebsocketErrored] = useState(false);

  // const [callbacks, setCallbacks] = useState([]);
  // const callbacks = useRef();
  const cbs = new Callbacks();
  const callbacks = useRef(cbs);
  // const callbacks = useRef(new Callbacks().bind(this));
  // const callbacks = useRef(cbs);

  let wssRef = useRef();
  useEffect(() => {
    console.log('WSSProvider mounted');
    let mounted = true;
    const wsUrl = process.env.REACT_APP_WS_URL || 'wss://admin.peterbe.com/ws';

    console.log(`Setting up WebSocket connection to ${wsUrl}`);
    // callbacks.current = new Callbacks();
    wssRef.current = new Sockette(wsUrl, {
      // setWss(
      //   new Sockette(wsUrl, {
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
        // console.log('GOT TO DO SOMETHING WITH', data);
        callbacks.current.send(data);
        //   onMessage(data);
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

  // console.log('CURRENT:', callbacks.current);
  var returnThese = {
    // register: callbacks.current ? callbacks.current.register : null,
    register: callbacks.current.register,
    wss: wssRef.current,
    connected,
    errored: websocketErrored,
  };
  // console.log('RETURNING', returnThese);
  return (
    <WSSContext.Provider value={returnThese}>{children}</WSSContext.Provider>
  );
}

export function useWSS() {
  return useContext(WSSContext);
}
