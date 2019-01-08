import auth0 from 'auth0-js';
import React from 'react';
import { formatDistance } from 'date-fns/esm';
import { BrowserRouter as Router, Link, Route, Switch } from 'react-router-dom';
import 'semantic-ui-css/semantic.min.css';
import { Container, Dropdown, Loader, Menu } from 'semantic-ui-react';
import './copy-of-highlight.css';
import './App.css';
import {
  OIDC_AUDIENCE,
  OIDC_CALLBACK_URL,
  OIDC_CLIENT_ID,
  OIDC_DOMAIN
} from './Config';
import Blogitems from './Blogitems';
import Comments from './Comments';
import Dashboard from './Dashboard';
import { AddBlogitem, EditBlogitem } from './EditBlogitem';
import OpenGraphImageBlogitem from './OpenGraphImageBlogitem';
import UploadImages from './UploadImages';
import PostProcessings from './PostProcessings';
import SearchResults from './SearchResults';

class App extends React.Component {
  state = {
    accessToken: null,
    userInfo: null
  };
  componentDidMount() {
    document.title = 'Peterbe.com Admin UI';
    this.authenticate();
  }

  // Sign in either by localStorage or by window.location.hash
  authenticate() {
    this.webAuth = new auth0.WebAuth({
      audience: OIDC_AUDIENCE,
      clientID: OIDC_CLIENT_ID,
      domain: OIDC_DOMAIN,
      redirectUri: OIDC_CALLBACK_URL,
      responseType: 'token id_token',
      scope: 'openid profile email'
    });

    this.webAuth.parseHash(
      { hash: window.location.hash },
      (err, authResult) => {
        if (err) {
          return console.error(err);
        }
        if (authResult && window.location.hash) {
          window.location.hash = '';
        }

        let startAccessTokenRefreshLoop = !!authResult;

        if (!authResult) {
          authResult = JSON.parse(localStorage.getItem('authResult'));
          if (authResult) {
            startAccessTokenRefreshLoop = true;
          }
          const expiresAt = JSON.parse(localStorage.getItem('expiresAt'));
          if (expiresAt && expiresAt - new Date().getTime() < 0) {
            // Oh no! It has expired.
            authResult = null;
          }
        }
        if (authResult) {
          // The contents of authResult depend on which authentication parameters were used.
          // It can include the following:
          // authResult.accessToken - access token for the API specified by `audience`
          // authResult.expiresIn - string with the access token's expiration time in seconds
          // authResult.idToken - ID token JWT containing user profile information
          this._postProcessAuthResult(authResult);
        }
        if (startAccessTokenRefreshLoop) {
          this.accessTokenRefreshLoop();
        }
      }
    );
  }

  _postProcessAuthResult = authResult => {
    if (authResult) {
      // Now you have the user's information
      this.setState({
        userInfo: authResult.idTokenPayload,
        accessToken: authResult.accessToken
      });

      const expiresAt = authResult.expiresIn * 1000 + new Date().getTime();
      if (authResult.state) {
        // XXX we could use authResult.state to redirect to where you
        // came from.
        delete authResult.state;
      }
      localStorage.setItem('authResult', JSON.stringify(authResult));
      localStorage.setItem('expiresAt', JSON.stringify(expiresAt));
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
    age -= 1000 * 30 * 60;
    const timeToRefresh = age < 0;

    if (timeToRefresh) {
      console.warn('Time to fresh the auth token!');
      this.webAuth.checkSession({}, (err, authResult) => {
        if (err) {
          if (err.error === 'login_required') {
            console.warn('Error in checkSession requires a new login');
            return this.authorize();
          } else {
            console.warn('Error trying to checkSession');
            return console.error(err);
          }
        }
        this._postProcessAuthResult(authResult);
      });
    } else {
      window.setTimeout(() => {
        if (!this.dismounted) {
          this.accessTokenRefreshLoop();
        }
      }, 1000 * 5 * 60);
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
      clientID: OIDC_CLIENT_ID,
      returnTo: rootUrl
    });
  };

  render() {
    return (
      <Router>
        <div>
          <Menu fixed="top" inverted>
            <Container>
              <Menu.Item header>
                {/* <Image size="mini" src="/logo.png" style={{ marginRight: '1.5em' }} /> */}
                <Link to="/">Peterbe.com Admin UI</Link>
              </Menu.Item>
              <Dropdown item simple text="Blogitems">
                <Dropdown.Menu>
                  <Dropdown.Item>
                    <Link to="/plog" style={{ color: '#000' }}>
                      Blogitems
                    </Link>
                  </Dropdown.Item>
                  <Dropdown.Item>
                    <Link to="/plog/add" style={{ color: '#000' }}>
                      Add new blogitem
                    </Link>
                  </Dropdown.Item>
                  {/* <Dropdown.Divider />
                  <Dropdown.Header>Header Item</Dropdown.Header>
                  <Dropdown.Item>
                    <i className="dropdown icon" />
                    <span className="text">Submenu</span>
                    <Dropdown.Menu>
                      <Dropdown.Item>List Item</Dropdown.Item>
                      <Dropdown.Item>List Item</Dropdown.Item>
                    </Dropdown.Menu>
                  </Dropdown.Item>
                  <Dropdown.Item>List Item</Dropdown.Item> */}
                </Dropdown.Menu>
              </Dropdown>
              <Menu.Item>
                <Link to="/plog/comments">Comments</Link>
              </Menu.Item>
              <Menu.Item>
                <Link to="/postprocessings">Post Processings</Link>
              </Menu.Item>
              <Menu.Item>
                <Link to="/searchresults">Search Results</Link>
              </Menu.Item>

              <Menu.Menu position="right">
                {this.state.userInfo ? (
                  <Menu.Item>
                    <img
                      alt="Avatar"
                      src={this.state.userInfo.picture}
                      title={`${this.state.userInfo.name} ${
                        this.state.userInfo.email
                      }`}
                    />
                  </Menu.Item>
                ) : null}
                {this.state.userInfo ? (
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

          <Container style={{ marginTop: '5em' }}>
            <Switch>
              <Route
                path="/"
                exact
                render={props => (
                  <Dashboard
                    {...props}
                    authorize={this.authorize}
                    accessToken={this.state.accessToken}
                  />
                )}
              />
              {/* <Route path="/comments" exact component={Comments} /> */}
              <SecureRoute
                path="/plog/comments"
                exact
                component={Comments}
                accessToken={this.state.accessToken}
              />
              <SecureRoute
                path="/plog"
                exact
                component={Blogitems}
                accessToken={this.state.accessToken}
              />
              <SecureRoute
                path="/plog/add"
                exact
                component={AddBlogitem}
                accessToken={this.state.accessToken}
              />
              <SecureRoute
                path="/plog/:oid/open-graph-image"
                component={OpenGraphImageBlogitem}
                accessToken={this.state.accessToken}
              />
              <SecureRoute
                path="/plog/:oid/images"
                component={UploadImages}
                accessToken={this.state.accessToken}
              />
              <SecureRoute
                path="/plog/:oid"
                component={EditBlogitem}
                accessToken={this.state.accessToken}
              />
              <SecureRoute
                path="/postprocessings"
                exact
                component={PostProcessings}
                accessToken={this.state.accessToken}
              />
              <SecureRoute
                path="/searchresults"
                exact
                component={SearchResults}
                accessToken={this.state.accessToken}
              />
              <Route component={NoMatch} />
            </Switch>
          </Container>

          {/* <Segment
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
          </Segment> */}
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

class SecureRoute extends React.Component {
  render() {
    const { accessToken, path } = this.props;
    if (!accessToken) {
      return (
        <Container>
          <Loader
            active
            size="massive"
            inline="centered"
            content="Waiting to log you in..."
            style={{ margin: '200px 0' }}
          />
        </Container>
      );
    }
    const Component = this.props.component;
    return (
      <Route
        path={path}
        render={props => {
          return <Component {...props} accessToken={accessToken} />;
        }}
      />
    );
  }
}
