import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';

/* Hack necessary to satisfy busted IE versions */
// https://github.com/facebook/create-react-app/issues/2856#issuecomment-317937629
// import 'core-js/fn/string/includes';
// import 'core-js/library/fn/set';

let initialValue = '';
let initialInput = document.querySelector('#root input[name="term"]');
if (initialInput) {
  initialValue = initialInput.value;
}
ReactDOM.render(
  <App initialValue={initialValue} />,
  document.getElementById('root')
);
