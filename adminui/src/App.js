import React, { Suspense, useEffect, useState } from 'react';
import { BrowserRouter as Router, Link, Route, Switch } from 'react-router-dom';
import useSWR from 'swr';
import 'semantic-ui-css/semantic.min.css';
import { Container, Dropdown, Loader, Menu } from 'semantic-ui-react';
import { SemanticToastContainer } from 'react-semantic-toasts';
import { toast } from 'react-semantic-toasts';
import 'react-semantic-toasts/styles/react-semantic-alert.css';
import './copy-of-highlight.css';
import './App.css';
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
function AddBlogitem(props) {
  return <AddOrEditBlogitem addOrEdit="add" {...props} />;
}
function EditBlogitem(props) {
  return <AddOrEditBlogitem addOrEdit="edit" {...props} />;
}

export default function App() {
  const [purgeUrlsCount, setPurgeUrlsCount] = useState(null);
  const [latestPostProcessing, setLatestPostProcessing] = useState(null);

  useEffect(() => {
    document.title = 'Peterbe.com Admin';
  }, []);

  const { data: user, error: whoamiError } = useSWR(
    '/api/v0/whoami',
    async (url) => {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`${response.status} on ${url}`);
      }
      const data = await response.json();
      if (data.is_authenticated) {
        return data;
      }
      return null;
    }
  );

  function authorize(returnUrl = null) {
    if (!returnUrl) {
      returnUrl = document.location.pathname;
    }
    const sp = new URLSearchParams();
    sp.set('next', returnUrl);
    document.location.href = `/oidc/authenticate/?${sp.toString()}`;
  }

  async function logOut() {
    const data = {
      csrfmiddlewaretoken: user.csrfmiddlewaretoken,
    };
    // XXX does this even work?
    await fetch('/oidc/logout/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  function onWebSocketMessage(msg) {
    // console.log('WS MESSAGE:', msg);
    if (msg.cdn_purge_urls !== undefined) {
      setPurgeUrlsCount(msg.cdn_purge_urls);
    } else if (msg.post_processed) {
      setLatestPostProcessing(msg.post_processed);
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
  }

  useEffect(() => {
    if (whoamiError) {
      toast({
        type: 'error',
        title: 'Fetch user error',
        description: `Error calling whoami API (${whoamiError})`,
        time: 7000,
        // size: null // https://github.com/academia-de-codigo/react-semantic-toasts/issues/40
      });
    }
  }, [whoamiError]);

  return (
    <Router>
      <div>
        <SemanticToastContainer />
        <Menu fixed="top" inverted>
          <Pulse onMessage={onWebSocketMessage} />
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
                <DropdownLink to="/plog/comments/geo" style={{ color: '#000' }}>
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
                {!!purgeUrlsCount && ` (${purgeUrlsCount})`}
              </Link>
            </Menu.Item>
            <Menu.Item>
              <Link to="/lyrics-page-healthcheck">Lyrics Page Healthcheck</Link>
            </Menu.Item>

            <Menu.Menu position="right">
              {user ? (
                <Menu.Item>
                  <img
                    alt="Avatar"
                    src={
                      user.picture_url ||
                      'https://www.peterbe.com/avatar.random.png'
                    }
                    title={`${user.username} ${user.email}`}
                  />
                </Menu.Item>
              ) : null}
              {user ? (
                <Menu.Item
                  name="logout"
                  onClick={async (event) => {
                    event.preventDefault();
                    await logOut();
                  }}
                />
              ) : (
                <Menu.Item
                  name="login"
                  onClick={(event) => {
                    event.preventDefault();
                    authorize();
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
                  <Dashboard {...props} user={user} authorize={authorize} />
                )}
              />
              <SecureRoute
                path="/plog/spam/patterns"
                exact
                component={SpamCommentPatterns}
                user={user}
              />
              <SecureRoute
                path="/plog/comments/geo"
                exact
                component={GeoComments}
                user={user}
              />
              <SecureRoute
                path="/plog/comments/counts"
                exact
                component={CommentCounts}
                user={user}
              />
              <SecureRoute
                path="/plog/comments/auto-approved-records"
                exact
                component={CommentAutoApproveds}
                user={user}
              />
              <SecureRoute
                path="/plog/comments"
                exact
                component={Comments}
                user={user}
              />
              <SecureRoute
                path="/plog/hits"
                exact
                component={BlogitemHits}
                user={user}
              />
              <SecureRoute
                path="/plog/realtimehits"
                exact
                component={RealtimeBlogitemHits}
                user={user}
              />
              <SecureRoute
                path="/plog"
                exact
                component={Blogitems}
                user={user}
              />
              <SecureRoute
                path="/plog/add"
                exact
                component={AddBlogitem}
                user={user}
              />
              <SecureRoute
                path="/plog/:oid/open-graph-image"
                component={OpenGraphImageBlogitem}
                user={user}
              />
              <SecureRoute
                path="/plog/:oid/images"
                component={UploadImages}
                user={user}
              />
              <SecureRoute
                path="/plog/:oid"
                component={EditBlogitem}
                user={user}
              />
              <SecureRoute
                path="/postprocessings"
                exact
                component={PostProcessings}
                user={user}
                latestPostProcessing={latestPostProcessing}
              />
              <SecureRoute
                path="/searchresults"
                exact
                component={SearchResults}
                user={user}
              />
              <SecureRoute
                path="/cdn"
                exact
                component={CDN}
                user={user}
                purgeUrlsCount={purgeUrlsCount}
              />
              <SecureRoute
                path="/lyrics-page-healthcheck"
                exact
                component={LyricsPageHealthcheck}
                user={user}
              />
              <SecureRoute
                path="/awspa"
                exact
                component={AWSPAItems}
                user={user}
              />
              <SecureRoute
                path="/awspa/search"
                exact
                component={AWSPASearch}
                user={user}
              />
              <SecureRoute
                path="/awspa/:id"
                exact
                component={AWSPAItem}
                user={user}
              />

              <Route component={NoMatch} />
            </Switch>
          </Suspense>
        </Container>
      </div>
    </Router>
  );
}

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

function NoMatch({ location }) {
  return (
    <div>
      <h3>
        No match for <code>{location.pathname}</code>
      </h3>
    </div>
  );
}

function SecureRoute(props) {
  const { user, path, component } = props;
  if (!user) {
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
  const Component = component;
  const outerProps = props;
  return (
    <Route
      path={path}
      render={(props) => {
        return <Component {...outerProps} {...props} user={user} />;
      }}
    />
  );
}
