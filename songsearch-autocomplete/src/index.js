import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';

const initialValue = document.querySelector('#root input[name="term"]').value
ReactDOM.render(
  <App initialValue={initialValue}/>, document.getElementById('root')
);
