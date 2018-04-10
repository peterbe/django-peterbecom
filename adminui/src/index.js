import React from 'react';
import ReactDOM from 'react-dom';
// import './index.css';
// import { apiClient } from 'mobx-rest';
// import adapter from 'mobx-rest-fetch-adapter';
import App from './App';
import registerServiceWorker from './registerServiceWorker';

// Initialize mob-rest API adapter
// const apiPath = 'http://localhost:8000/plogadmin';
// const apiPath = '/plogadmin';
// apiClient(adapter, { apiPath });

ReactDOM.render(<App />, document.getElementById('root'));
registerServiceWorker();
