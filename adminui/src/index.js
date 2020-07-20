import React from 'react';
import ReactDOM from 'react-dom';
import './index.css';
import App from './App';

import { WSSProvider } from './WSSContext';

// Commented out till semantic-ui-react releases something >0.88.2 to fix all the warnings.
// const app = (
//   <React.StrictMode>
//     <WSSProvider>
//       <App />
//     </WSSProvider>
//   </React.StrictMode>
// );
const app = (
  <WSSProvider>
    <App />
  </WSSProvider>
);
ReactDOM.render(app, document.getElementById('root'));
