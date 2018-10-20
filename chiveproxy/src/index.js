import React from 'react';
import ReactDOM from 'react-dom';
import './index.sass';
import App from './App';
import * as serviceWorker from './serviceWorker';

ReactDOM.render(<App />, document.getElementById('root'));

// Learn more about service workers: http://bit.ly/CRA-PWA
serviceWorker.register({
  onUpdate: () => {
    window.location.reload();
  }
});
