import React from 'react';
import {
  Button,
  Container,
  Dimmer,
  Header,
  Icon,
  Loader,
  Segment
} from 'semantic-ui-react';
import { ShowServerError } from './Common';
import XCacheAnalyze from './XCacheAnalyze';

function defaultLoopSeconds(default_ = 60) {
  try {
    return parseInt(
      window.localStorage.getItem('lyrics-page-healthcheck-loopseconds') ||
        default_,
      10
    );
  } catch (ex) {
    return default_;
  }
}

class LyricsPageHealthcheck extends React.Component {
  state = {
    health: null,
    loading: false,
    fetched: null,
    serverError: null,
    loopSeconds: defaultLoopSeconds()
  };
  componentDidMount() {
    document.title = 'Lyrics Page Healthcheck';
    this.startLoop();
  }
  componentWillUnmount() {
    this.dismounted = true;
    if (this._loop) window.clearTimeout(this._loop);
  }

  startLoop = () => {
    this.loadHealth();
    if (this._loop) {
      window.clearTimeout(this._loop);
    }
    if (this.state.loopSeconds) {
      this._loop = window.setTimeout(() => {
        this.startLoop();
      }, this.state.loopSeconds * 1000);
    }
  };

  loadHealth = (url = null) => {
    this.setState({ loading: true }, async () => {
      let response;
      let URL = '/api/v0/lyrics-page-healthcheck';
      if (url) {
        URL += `?url=${encodeURI(url)}`;
      }
      try {
        response = await fetch(URL);
      } catch (ex) {
        return this.setState({
          loading: false,
          serverError: ex,
          fetched: new Date()
        });
      }

      if (this.dismounted) {
        return;
      }
      if (response.ok) {
        const result = await response.json();
        if (url) {
          if (result.health.length !== 1) {
            throw new Error('Not implemented');
          }
          // Update just one from the existing array.
          const health = this.state.health.map(h => {
            if (h.url === url) {
              return result.health[0];
            } else {
              return h;
            }
          });
          this.setState({
            health,
            loading: false,
            serverError: null,
            fetched: new Date()
          });
        } else {
          this.setState({
            health: result.health,
            loading: false,
            serverError: null,
            fetched: new Date()
          });
        }
      } else {
        this.setState({
          loading: false,
          serverError: response,
          fetched: new Date()
        });
      }
    });
  };

  checkURL = url => {
    this.loadHealth(url);
  };

  render() {
    const { health, fetched, loopSeconds, loading, serverError } = this.state;
    let nextFetch = null;
    if (fetched) {
      nextFetch = new Date(fetched.getTime() + loopSeconds * 1000);
    }

    return (
      <Container>
        <Header as="h1">Lyrics Page Healthcheck</Header>
        <ShowServerError error={serverError} />
        <Segment basic>
          <Dimmer active={loading} inverted>
            <Loader inverted>Loading</Loader>
          </Dimmer>
          {health && (
            <ShowHealth
              health={health}
              checkURL={this.checkURL}
              accessToken={this.props.accessToken}
            />
          )}
          {nextFetch && <ShowLoopCountdown nextFetch={nextFetch} />}
        </Segment>
      </Container>
    );
  }
}

export default LyricsPageHealthcheck;

function ShowLoopCountdown({ nextFetch }) {
  const [left, updateLeft] = React.useState(
    Math.ceil((nextFetch.getTime() - new Date().getTime()) / 1000)
  );
  React.useEffect(() => {
    const loop = window.setInterval(() => {
      updateLeft(
        Math.ceil((nextFetch.getTime() - new Date().getTime()) / 1000)
      );
    }, 1000);
    return () => window.clearInterval(loop);
  }, [nextFetch]);

  if (left > 120) {
    return <small>Refreshing in {Math.floor(left / 60)} minutes.</small>;
  }
  if (left > 0) {
    return <small>Refreshing in {left} seconds.</small>;
  } else {
    return <small>Refreshing now.</small>;
  }
}

function ShowHealth({ health, checkURL, accessToken }) {
  const [xcacheAnalyzeAll, setXCacheAnalyzeAll] = React.useState(null);

  function startAllXCacheAnalyze() {
    const todo = new Map();
    health.forEach((page, i) => {
      todo.set(page.url, i === 0);
    });
    setXCacheAnalyzeAll(todo);
  }

  function stopAllXCacheAnalyze() {
    setXCacheAnalyzeAll(null);
  }

  function nextAllXCacheAnalyze(url) {
    if (xcacheAnalyzeAll === null) {
      // It has been stopped!
      return;
    }
    const todo = new Map();
    let first = true;
    for (let u of xcacheAnalyzeAll.keys()) {
      if (u !== url) {
        todo.set(u, first);
        first = false;
      }
    }
    if (!todo.size) {
      // Start over!
      health.forEach((page, i) => {
        todo.set(page.url, i === 0);
      });
    }
    setXCacheAnalyzeAll(todo);
  }

  function isAutoStart(url) {
    if (xcacheAnalyzeAll) {
      return xcacheAnalyzeAll.get(url) || false;
    }
    return false;
  }

  console.log(xcacheAnalyzeAll);
  return (
    <div>
      <div style={{ textAlign: 'right' }}>
        <Button
          onClick={event => {
            startAllXCacheAnalyze();
          }}
          disabled={!!xcacheAnalyzeAll}
        >
          X-Cache Analyze All
        </Button>
        {!!xcacheAnalyzeAll && (
          <Button onClick={() => stopAllXCacheAnalyze()}>Stop</Button>
        )}
      </div>

      <Segment.Group>
        {health.map(page => {
          let color = '';
          let name = '';
          if (page.health === 'WARNING') {
            color = 'orange';
            name = 'warning sign';
          } else if (page.health === 'ERROR') {
            color = 'red';
            name = 'thumbs down';
          } else if (page.health === 'OK') {
            color = 'green';
            name = 'thumbs up';
          } else {
            throw new Error(`Unrecognized enum ${page.health}`);
          }
          return (
            <Segment key={page.url}>
              <a href={page.url}>{page.url}</a>{' '}
              <a
                href={`/cdn?url=${encodeURI(page.url)}`}
                rel="noopener noreferrer"
                target="_blank"
                title="Do a CDN probe"
              >
                <small>(CDN probe)</small>
              </a>{' '}
              <Button
                size="mini"
                onClick={event => {
                  checkURL(page.url);
                }}
              >
                Check again
              </Button>{' '}
              <Icon name={name} color={color} size="large" />{' '}
              <small>took {`${(1000 * page.took).toFixed(1)}ms`}</small>
              {page.errors && page.errors.length ? (
                <ShowErrors errors={page.errors} />
              ) : null}{' '}
              <XCacheAnalyze
                accessToken={accessToken}
                url={page.url}
                start={isAutoStart(page.url)}
                finished={() => {
                  nextAllXCacheAnalyze(page.url);
                }}
                minimalButton={true}
              />
            </Segment>
          );
        })}
      </Segment.Group>
    </div>
  );
}

function ShowErrors({ errors }) {
  return (
    <div>
      {errors.map((error, i) => (
        <p key={i}>{error}</p>
      ))}
    </div>
  );
}
