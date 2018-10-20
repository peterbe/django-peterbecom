import React from 'react';
import { BrowserRouter as Router, Route, Switch } from 'react-router-dom';

import Home from './Home';
import Card from './Card';

class App extends React.Component {
  render() {
    return (
      <Router>
        <div>
          {/* <Nav /> */}
          <section className="section">
            <Switch>
              <Route path="/" exact component={Home} />
              <Route path="/([a-f0-9]{8})/(previous|next)" component={Home} />
              <Route path="/([a-f0-9]{8})" component={Card} />
              <Route component={NoMatch} />
            </Switch>
          </section>
        </div>
      </Router>
    );
  }
}

export default App;

const NoMatch = ({ location }) => (
  <div>
    <h3>
      No match for <code>{location.pathname}</code>
    </h3>
  </div>
);

// class Nav extends React.PureComponent {
//   state = { open: false };
//   render() {
//     return (
//       <nav className="navbar" role="navigation" aria-label="main navigation">
//         <div className="navbar-brand">
//           <Link to="/" className="navbar-item">
//             <img src={logo} alt="The Chive Proxy" height="28" />
//           </Link>
//           <a
//             role="button"
//             className={
//               this.state.open
//                 ? 'is-active navbar-burger burger'
//                 : 'navbar-burger burger'
//             }
//             aria-label="menu"
//             aria-expanded="false"
//             data-target="navbarBasicExample"
//             onClick={event => {
//               event.preventDefault();
//               this.setState({ open: !this.state.open });
//             }}
//           >
//             <span aria-hidden="true" />
//             <span aria-hidden="true" />
//             <span aria-hidden="true" />
//           </a>
//         </div>

//         <div
//           id="navbarBasicExample"
//           className={this.state.open ? 'is-active navbar-menu' : 'navbar-menu'}
//         >
//           <div className="navbar-start">
//             <Link to="/" className="navbar-item">
//               Home
//             </Link>
//             {/* <a className="navbar-item">Documentation</a> */}
//           </div>
//         </div>

//         <div className="navbar-end">
//           <div className="navbar-item">
//             {/* <div class="buttons">
//           <a class="button is-primary">
//             <strong>Sign up</strong>
//           </a>
//           <a class="button is-light">
//             Log in
//           </a>
//         </div> */}
//           </div>
//         </div>
//       </nav>
//     );
//   }
// }
