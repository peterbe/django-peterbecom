import React from 'react';
import {
  Container,
  Dimmer,
  Header,
  Icon,
  Loader,
  Segment
} from 'semantic-ui-react';
import { ShowServerError } from './Common';

function defaultLoopSeconds(default_ = 60) {
  try {
    return parseInt(
      window.localStorage.getItem('lyrics-page-healthcheck-loopseconds') ||
        default_,
      60
    );
  } catch (ex) {
    return default_;
  }
}

class LyricsPageHealthcheck extends React.Component {
  state = {
    health: null,
    loading: false,
    serverError: null,
    loopSeconds: defaultLoopSeconds()
  };
  componentDidMount() {
    document.title = 'Lyrics Page Healthcheck';
    this.startLoop();
    // this.setState({ loading: true }, this.loadHealth);
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

  loadHealth = () => {
    this.setState({ loading: true }, async () => {
      let response;
      let url = '/api/v0/lyrics-page-healthcheck';
      try {
        response = await fetch(url);
      } catch (ex) {
        return this.setState({ loading: false, serverError: ex });
      }

      if (this.dismounted) {
        return;
      }
      if (response.ok) {
        const result = await response.json();
        this.setState({
          health: result.health,
          loading: false,
          serverError: null
        });
      } else {
        this.setState({ loading: false, serverError: response });
      }
    });
  };

  render() {
    const { health, loading, serverError } = this.state;
    return (
      <Container>
        <Header as="h1">Lyrics Page Healthcheck</Header>
        <ShowServerError error={serverError} />
        <Segment basic>
          <Dimmer active={loading} inverted>
            <Loader inverted>Loading</Loader>
          </Dimmer>
          {health && <ShowHealth health={health} />}
        </Segment>
      </Container>
    );
  }
}

export default LyricsPageHealthcheck;

function ShowHealth({ health }) {
  return (
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
            <Icon name={name} color={color} size="large" />
            {page.errors && page.errors.length ? (
              <ShowErrors errors={page.errors} />
            ) : null}
          </Segment>
        );
      })}
    </Segment.Group>
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
