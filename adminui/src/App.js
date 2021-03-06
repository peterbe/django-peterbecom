import auth0 from 'auth0-js';
import React, { Suspense } from 'react';
import { formatDistance } from 'date-fns/esm';
import { BrowserRouter as Router, Link, Route, Switch } from 'react-router-dom';
import 'semantic-ui-css/semantic.min.css';
import { Container, Dropdown, Loader, Menu } from 'semantic-ui-react';
import { SemanticToastContainer } from 'react-semantic-toasts';
import { toast } from 'react-semantic-toasts';
import 'react-semantic-toasts/styles/react-semantic-alert.css';
import './copy-of-highlight.css';
import './App.css';
import {
  OIDC_AUDIENCE,
  OIDC_CALLBACK_URL,
  OIDC_CLIENT_ID,
  OIDC_DOMAIN,
} from './Config';
import Pulse from './Pulse';
import Comments from './Comments';
import Dashboard from './Dashboard';

const Blogitems = React.lazy(() => import('./Blogitems'));
const AddOrEditBlogitem = React.lazy(() => import('./EditBlogitem'));
const OpenGraphImageBlogitem = React.lazy(() =>
  import('./OpenGraphImageBlogitem')
);
const UploadImages = React.lazy(() => import('./UploadImages'));
const PostProcessings = React.lazy(() => import('./PostProcessings'));
const SearchResults = React.lazy(() => import('./SearchResults'));
const BlogitemHits = React.lazy(() => import('./BlogitemHits'));
const RealtimeBlogitemHits = React.lazy(() => import('./RealtimeBlogitemHits'));
const CDN = React.lazy(() => import('./CDN'));
const LyricsPageHealthcheck = React.lazy(() =>
  import('./LyricsPageHealthcheck')
);
const SpamCommentPatterns = React.lazy(() => import('./SpamCommentPatterns'));
const GeoComments = React.lazy(() => import('./GeoComments'));
const CommentCounts = React.lazy(() => import('./CommentCounts'));
const CommentAutoApproveds = React.lazy(() => import('./CommentAutoApproveds'));
const AWSPAItems = React.lazy(() => import('./AWSPAItems'));
const AWSPAItem = React.lazy(() => import('./AWSPAItem'));
const AWSPASearch = React.lazy(() => import('./AWSPASearch'));

// These exist so I can have just 1 *default* export from the 'EditBlogItem.js'
class AddBlogitem extends React.Component {
  render() {
    return <AddOrEditBlogitem addOrEdit="add" {...this.props} />;
  }
}

class EditBlogitem extends React.Component {
  render() {
    return <AddOrEditBlogitem addOrEdit="edit" {...this.props} />;
  }
}

class App extends React.Component {
  state = {
    accessToken: null,
    userInfo: null,
    purgeUrlsCount: null,
    latestPostProcessing: null,
  };
  componentDidMount() {
    document.title = 'Peterbe.com Admin';
    this.authenticate();
    this.fetchPurgeURLsCount();
  }

  componentWillUnmount() {
    this.dismounted = true;
  }

  // Sign in either by localStorage or by window.location.hash
  authenticate() {
    this.webAuth = new auth0.WebAuth({
      audience: OIDC_AUDIENCE,
      clientID: OIDC_CLIENT_ID,
      domain: OIDC_DOMAIN,
      redirectUri: OIDC_CALLBACK_URL,
      responseType: 'token id_token',
      scope: 'openid profile email',
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

  _postProcessAuthResult = (authResult) => {
    if (authResult) {
      // Now you have the user's information
      const update = {
        userInfo: authResult.idTokenPayload,
        accessToken: authResult.accessToken,
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
      appState: { returnUrl },
    });
  };

  logOut = () => {
    localStorage.removeItem('expiresAt');
    localStorage.removeItem('authResult');
    const rootUrl = `${window.location.protocol}//${window.location.host}/`;
    this.webAuth.logout({
      clientID: OIDC_CLIENT_ID,
      returnTo: rootUrl,
    });
  };

  onWebSocketMessage = (msg) => {
    // console.log('WS MESSAGE:', msg);
    if (msg.cdn_purge_urls !== undefined) {
      if (!this.dismounted)
        this.setState({ purgeUrlsCount: msg.cdn_purge_urls });
    } else if (msg.post_processed) {
      if (!this.dismounted) {
        this.setState({ latestPostProcessing: msg.post_processed });
      }
    } else {
      let description = JSON.stringify(msg);
      if (typeof msg === 'object') {
        // Perhaps we can do better!
        if (msg.searched) {
          description = `Someone searched for '${msg.searched.q}' and found ${msg.searched.documents_found} documents.`;
        }
      }
      if (!document.hidden) {
        toast({
          type: 'info',
          title: 'Pulse message',
          description,
          time: 7000,
          // size: null // https://github.com/academia-de-codigo/react-semantic-toasts/issues/40
        });
        // toastDocumentTitle({
        //   text: description,
        //   time: 5000
        // });
      }
    }
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
            <Pulse onMessage={this.onWebSocketMessage} />
            <Container>
              <Menu.Item header>
                <Link to="/">Peterbe.com Admin</Link>
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
                    to="/plog/comments/auto-approved-records"
                    style={{ color: '#000' }}
                  >
                    Auto Approved Records
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
                    onClick={(event) => {
                      event.preventDefault();
                      this.logOut();
                    }}
                  />
                ) : (
                  <Menu.Item
                    name="login"
                    onClick={(event) => {
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
                  render={(props) => (
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
                  path="/plog/comments/auto-approved-records"
                  exact
                  component={CommentAutoApproveds}
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
                  latestPostProcessing={this.state.latestPostProcessing}
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
                  purgeUrlsCount={this.state.purgeUrlsCount}
                />
                <SecureRoute
                  path="/lyrics-page-healthcheck"
                  exact
                  component={LyricsPageHealthcheck}
                  accessToken={this.state.accessToken}
                />
                <SecureRoute
                  path="/awspa"
                  exact
                  component={AWSPAItems}
                  accessToken={this.state.accessToken}
                />
                <SecureRoute
                  path="/awspa/search"
                  exact
                  component={AWSPASearch}
                  accessToken={this.state.accessToken}
                />
                <SecureRoute
                  path="/awspa/:id"
                  exact
                  component={AWSPAItem}
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
        onClick={(event) => {
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
        render={(props) => {
          return (
            <Component {...this.props} {...props} accessToken={accessToken} />
          );
        }}
      />
    );
  }
}
