import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';

let initialValue = ''
let initialInput = document.querySelector('#root input[name="term"]')
if (initialInput) {
  initialValue = initialInput.value
}
ReactDOM.render(
  <App initialValue={initialValue}/>, document.getElementById('root')
);
