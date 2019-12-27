import auth0 from 'auth0-js';
import React, { Suspense, lazy } from 'react';
import { formatDistance } from 'date-fns/esm';
import { BrowserRouter as Router, Link, Route, Switch } from 'react-router-dom';
import 'semantic-ui-css/semantic.min.css';
import { Container, Dropdown, Loader, Menu } from 'semantic-ui-react';
import { SemanticToastContainer } from 'react-semantic-toasts';
import 'react-semantic-toasts/styles/react-semantic-alert.css';
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
import AWSPABlogitem from './AWSPABlogitem';
import UploadImages from './UploadImages';
// import PostProcessings from './PostProcessings';
// import SearchResults from './SearchResults';
// import BlogitemHits from './BlogitemHits';
// import RealtimeBlogitemHits from './RealtimeBlogitemHits';
// import CDN from './CDN';
// import LyricsPageHealthcheck from './LyricsPageHealthcheck';
// import SpamCommentPatterns from './SpamCommentPatterns';
// import GeoComments from './GeoComments';
// import CommentCounts from './CommentCounts';
const PostProcessings = lazy(() => import('./PostProcessings'));
const SearchResults = lazy(() => import('./SearchResults'));
const BlogitemHits = lazy(() => import('./BlogitemHits'));
const RealtimeBlogitemHits = lazy(() => import('./RealtimeBlogitemHits'));
const CDN = lazy(() => import('./CDN'));
const LyricsPageHealthcheck = lazy(() => import('./LyricsPageHealthcheck'));
const SpamCommentPatterns = lazy(() => import('./SpamCommentPatterns'));
const GeoComments = lazy(() => import('./GeoComments'));
const CommentCounts = lazy(() => import('./CommentCounts'));

// Not a 'const' because we're going to cheekily increase every time it
// gets mutated later.
let CDN_PURGE_URLS_LOOP_SECONDS = 10;

class App extends React.Component {
  state = {
    accessToken: null,
    userInfo: null,
    purgeUrlsCount: null
  };
  componentDidMount() {
    document.title = 'Peterbe.com Admin UI';
    this.authenticate();

    // Delay this loop a little so that it starts after other more important
    // XHR fetches.
    setTimeout(() => {
      !this.dismounted && this.startCDNPurgeURLsLoop();
    }, 1000);
  }

  componentWillUnmount() {
    this.dismounted = true;
    if (this._cdnPurgeURLsLoop) window.clearTimeout(this._cdnPurgeURLsLoop);
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

        // The contents of authResult depend on which authentication parameters were used.
        // It can include the following:
        // authResult.accessToken - access token for the API specified by `audience`
        // authResult.expiresIn - string with the access token's expiration time in seconds
        // authResult.idToken - ID token JWT containing user profile information
        this._postProcessAuthResult(authResult);

        if (startAccessTokenRefreshLoop) {
          this.accessTokenRefreshLoop();
        }
      }
    );
  }

  _postProcessAuthResult = authResult => {
    if (authResult) {
      // Now you have the user's information
      const update = {
        userInfo: authResult.idTokenPayload,
        accessToken: authResult.accessToken
      };
      const expiresAt = authResult.expiresIn * 1000 + new Date().getTime();
      let redirectTo = null;
      if (authResult.appState) {
        if (authResult.appState.returnUrl) {
          redirectTo = authResult.appState.returnUrl;
        }
        delete authResult.appState;
      }
      localStorage.setItem('authResult', JSON.stringify(authResult));
      localStorage.setItem('expiresAt', JSON.stringify(expiresAt));
      this.setState(update, () => {
        if (redirectTo && redirectTo !== document.location.pathname) {
          // Horrible! But how are you supposed to do this?!
          document.location.href = redirectTo;
        }
      });
    } else {
      if (window.location.pathname !== '/') {
        this.authorize();
      }
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

  authorize = (returnUrl = null) => {
    if (!returnUrl) {
      returnUrl = document.location.pathname;
    }
    this.webAuth.authorize({
      appState: { returnUrl }
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

  startCDNPurgeURLsLoop = () => {
    this.fetchPurgeURLsCount();
    if (this._cdnPurgeURLsLoop) {
      window.clearTimeout(this._cdnPurgeURLsLoop);
    }
    this._cdnPurgeURLsLoop = window.setTimeout(() => {
      this.startCDNPurgeURLsLoop();
      // Just a little hack. This way the timeout happens more and more rarely
      // as time goes by. Just to avoid it running too frequently when the tab
      // gets left open. Weird but fun. Perhaps delete some day.
      CDN_PURGE_URLS_LOOP_SECONDS++;
    }, 1000 * CDN_PURGE_URLS_LOOP_SECONDS);
  };

  fetchPurgeURLsCount = async () => {
    let response;
    let url = '/api/v0/cdn/purge/urls/count';
    try {
      response = await fetch(url);
    } catch (ex) {
      console.warn(`Unable to call ${url}: ${ex.toString()}`);
      return;
    }
    if (!this.dismounted && response.ok) {
      const data = await response.json();
      this.setState({ purgeUrlsCount: data.purge_urls.count });
    }
  };

  render() {
    return (
      <Router>
        <div>
          <SemanticToastContainer />
          <Menu fixed="top" inverted>
            <Container>
              <Menu.Item header>
                <Link to="/">Peterbe.com Admin UI</Link>
              </Menu.Item>
              <Dropdown item simple text="Blogitems">
                <Dropdown.Menu>
                  <DropdownLink to="/plog">Blogitems</DropdownLink>
                  <DropdownLink to="/plog/add">Add new blogitem</DropdownLink>
                  <DropdownLink to="/plog/realtimehits">
                    Realtime Hits
                  </DropdownLink>
                  <DropdownLink to="/plog/hits">Hits</DropdownLink>
                  <DropdownLink to="/plog/spam/patterns">
                    Spam Comment Patterns
                  </DropdownLink>
                </Dropdown.Menu>
              </Dropdown>
              <Dropdown item simple text="Comments">
                <Dropdown.Menu>
                  <DropdownLink to="/plog/comments" style={{ color: '#000' }}>
                    All comments
                  </DropdownLink>
                  <DropdownLink
                    to="/plog/comments?unapproved=only"
                    style={{ color: '#000' }}
                  >
                    Unapproved
                  </DropdownLink>
                  <DropdownLink
                    to="/plog/comments?autoapproved=only"
                    style={{ color: '#000' }}
                  >
                    Autoapproved
                  </DropdownLink>
                  <DropdownLink
                    to="/plog/comments/counts"
                    style={{ color: '#000' }}
                  >
                    Counts
                  </DropdownLink>
                  <DropdownLink
                    to="/plog/comments/geo"
                    style={{ color: '#000' }}
                  >
                    Geo
                  </DropdownLink>
                </Dropdown.Menu>
              </Dropdown>
              <Menu.Item>
                <Link to="/postprocessings">Post Processings</Link>
              </Menu.Item>
              <Menu.Item>
                <Link to="/searchresults">Search Results</Link>
              </Menu.Item>
              <Menu.Item>
                <Link to="/cdn">
                  CDN
                  {!!this.state.purgeUrlsCount &&
                    ` (${this.state.purgeUrlsCount})`}
                </Link>
              </Menu.Item>
              <Menu.Item>
                <Link to="/lyrics-page-healthcheck">
                  Lyrics Page Healthcheck
                </Link>
              </Menu.Item>

              <Menu.Menu position="right">
                {this.state.userInfo ? (
                  <Menu.Item>
                    <img
                      alt="Avatar"
                      src={this.state.userInfo.picture}
                      title={`${this.state.userInfo.name} ${this.state.userInfo.email}`}
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
            <Suspense fallback={<div>Loading...</div>}>
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
                <SecureRoute
                  path="/plog/spam/patterns"
                  exact
                  component={SpamCommentPatterns}
                  accessToken={this.state.accessToken}
                />
                <SecureRoute
                  path="/plog/comments/geo"
                  exact
                  component={GeoComments}
                  accessToken={this.state.accessToken}
                />
                <SecureRoute
                  path="/plog/comments/counts"
                  exact
                  component={CommentCounts}
                  accessToken={this.state.accessToken}
                />
                <SecureRoute
                  path="/plog/comments"
                  exact
                  component={Comments}
                  accessToken={this.state.accessToken}
                />
                <SecureRoute
                  path="/plog/hits"
                  exact
                  component={BlogitemHits}
                  accessToken={this.state.accessToken}
                />
                <SecureRoute
                  path="/plog/realtimehits"
                  exact
                  component={RealtimeBlogitemHits}
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
                  path="/plog/:oid/awspa"
                  component={AWSPABlogitem}
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
                <SecureRoute
                  path="/cdn"
                  exact
                  component={CDN}
                  accessToken={this.state.accessToken}
                />
                <SecureRoute
                  path="/lyrics-page-healthcheck"
                  exact
                  component={LyricsPageHealthcheck}
                  accessToken={this.state.accessToken}
                />

                <Route component={NoMatch} />
              </Switch>
            </Suspense>
          </Container>
        </div>
      </Router>
    );
  }
}

export default App;

function DropdownLink({ children, ...props }) {
  return (
    <Dropdown.Item>
      <Link
        {...props}
        style={{ color: 'black' }}
        onClick={event => {
          event.target.blur();
        }}
      >
        {children}
      </Link>
    </Dropdown.Item>
  );
}

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
