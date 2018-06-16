import React from 'react';
import { observer } from 'mobx-react';
import auth0 from 'auth0-js';
import './App.css';
import 'semantic-ui-css/semantic.min.css';
import { BrowserRouter as Router, Route, Switch, Link } from 'react-router-dom';
import { Container, Dropdown, List, Menu, Segment } from 'semantic-ui-react';
import { formatDistance } from 'date-fns/esm';

import Dashboard from './Dashboard';
import Blogitems from './Blogitems';
import EditBlogitem from './EditBlogitem';
import {
  OIDC_DOMAIN,
  OIDC_CLIENT_ID,
  OIDC_CALLBACK_URL,
  OIDC_AUDIENCE
} from './Config';
import store from './Store';

export default observer(
  class App extends React.Component {
    componentDidMount() {
      this.authenticate();
    }
    // Sign in either by localStorage or by window.location.hash
    authenticate() {
      this.webAuth = new auth0.WebAuth({
        domain: OIDC_DOMAIN,
        clientID: OIDC_CLIENT_ID,
        redirectUri: OIDC_CALLBACK_URL,
        audience: OIDC_AUDIENCE,
        responseType: 'token id_token',
        scope: 'openid profile email'
      });

      this.webAuth.parseHash(
        { hash: window.location.hash },
        (err, authResult) => {
          if (err) {
            return console.error(err);
          }

          if (!authResult) {
            authResult = JSON.parse(localStorage.getItem('authResult'));
          }

          // The contents of authResult depend on which authentication parameters were used.
          // It can include the following:
          // authResult.accessToken - access token for the API specified by `audience`
          // authResult.expiresIn - string with the access token's expiration time in seconds
          // authResult.idToken - ID token JWT containing user profile information
          this._postProcessAuthResult(authResult);
        }
      );
    }

    _postProcessAuthResult = authResult => {
      if (authResult) {
        this.webAuth.client.userInfo(authResult.accessToken, (err, user) => {
          if (err) {
            store.user.setServerError(err);
            return console.error(err);
          }
          // Now you have the user's information
          store.user.setUserInfo(user);
          store.user.setServerError(null);
          store.user.setAccessToken(authResult.accessToken);

          const expiresAt = authResult.expiresIn * 1000 + new Date().getTime();
          if (authResult.state) {
            delete authResult.state;
          }
          localStorage.setItem('authResult', JSON.stringify(authResult));
          localStorage.setItem('expiresAt', JSON.stringify(expiresAt));
          this.accessTokenRefreshLoop();
        });
      }
    };

    accessTokenRefreshLoop = () => {
      // Return true if the access token has expired (or is about to expire)
      const expiresAt = JSON.parse(localStorage.getItem('expiresAt'));
      // 'age' in milliseconds
      let age = expiresAt - new Date().getTime();
      console.log(
        'accessToken expires in',
        formatDistance(expiresAt, new Date())
      );
      // Consider the accessToken to be expired if it's about to expire
      // in 30 minutes.
      age -= 30 * 60 * 1000;
      const timeToRefresh = age < 0;

      if (timeToRefresh) {
        this.webAuth.checkSession({}, (err, authResult) => {
          if (err) {
            console.warn('Error trying to checkSession');
            return console.error(err);
          }
          this._postProcessAuthResult(authResult);
        });
      } else {
        window.setTimeout(() => {
          if (!this.dismounted) {
            this.accessTokenRefreshLoop();
          }
        }, 5 * 60 * 1000);
        // }, 10 * 1000);
      }
    };

    authorize = () => {
      this.webAuth.authorize({
        // state: returnUrl,
        state: '/'
      });
    };

    logOut = () => {
      localStorage.removeItem('expiresAt');
      localStorage.removeItem('authResult');
      const rootUrl = `${window.location.protocol}//${window.location.host}/`;
      this.webAuth.logout({
        returnTo: rootUrl,
        clientID: OIDC_CLIENT_ID
      });
    };

    render() {
      return (
        <Router>
          <div>
            <Menu fixed="top" inverted>
              <Container>
                <Menu.Item as="a" header>
                  {/* <Image size="mini" src="/logo.png" style={{ marginRight: '1.5em' }} /> */}
                  Peterbe.com Admin UI
                </Menu.Item>
                <Menu.Item>
                  <Link to="/">Home</Link>
                </Menu.Item>
                <Menu.Item>
                  <Link to="/blogitems">Blogitems</Link>
                </Menu.Item>

                <Dropdown item simple text="Dropdown">
                  <Dropdown.Menu>
                    <Dropdown.Item>List Item</Dropdown.Item>
                    <Dropdown.Item>List Item</Dropdown.Item>
                    <Dropdown.Divider />
                    <Dropdown.Header>Header Item</Dropdown.Header>
                    <Dropdown.Item>
                      <i className="dropdown icon" />
                      <span className="text">Submenu</span>
                      <Dropdown.Menu>
                        <Dropdown.Item>List Item</Dropdown.Item>
                        <Dropdown.Item>List Item</Dropdown.Item>
                      </Dropdown.Menu>
                    </Dropdown.Item>
                    <Dropdown.Item>List Item</Dropdown.Item>
                  </Dropdown.Menu>
                </Dropdown>

                <Menu.Menu position="right">
                  {store.user.userInfo ? (
                    <Menu.Item>
                      <img
                        alt="Avatar"
                        src={store.user.userInfo.picture}
                        title={`${store.user.userInfo.name} ${
                          store.user.userInfo.email
                        }`}
                      />
                    </Menu.Item>
                  ) : null}
                  {store.user.userInfo ? (
                    <Menu.Item
                      name="logout"
                      onClick={event => {
                        event.preventDefault();
                        this.logOut();
                      }}
                    />
                  ) : (
                    <Menu.Item
                      name="login"
                      onClick={event => {
                        event.preventDefault();
                        this.authorize();
                      }}
                    />
                  )}
                </Menu.Menu>
              </Container>
            </Menu>

            <Container style={{ marginTop: '7em' }}>
              <Switch>
                <Route
                  path="/"
                  exact
                  render={props => (
                    <Dashboard {...props} authorize={this.authorize} />
                  )}
                />
                <Route path="/blogitems" exact component={Blogitems} />
                <Route path="/blogitems/:id" component={EditBlogitem} />
                {/* <Route
                  path="/blogitems/:id"
                  render={props => (
                    <EditBlogitem
                      {...props}
                      accessToken={store.user.accessToken}
                    />
                  )}
                /> */}
                {/* <Redirect from="/old-match" to="/will-match" /> */}
                {/* <Route path="/will-match" component={WillMatch} /> */}
                <Route component={NoMatch} />
              </Switch>
            </Container>

            <Segment
              inverted
              vertical
              style={{ margin: '5em 0em 0em', padding: '5em 0em' }}
            >
              <Container textAlign="center">
                <List horizontal inverted divided link>
                  <List.Item as="a" href="#">
                    Site Map
                  </List.Item>
                  <List.Item as="a" href="#">
                    Contact Us
                  </List.Item>
                  <List.Item as="a" href="#">
                    Terms and Conditions
                  </List.Item>
                  <List.Item as="a" href="#">
                    Privacy Policy
                  </List.Item>
                </List>
              </Container>
            </Segment>
          </div>
        </Router>
      );
    }
  }
);

// export default App;

const NoMatch = ({ location }) => (
  <div>
    <h3>
      No match for <code>{location.pathname}</code>
    </h3>
  </div>
);
