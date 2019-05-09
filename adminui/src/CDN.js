import React from 'react';
import {
  Button,
  Container,
  Header,
  Icon,
  Input,
  Loader,
  Table,
  Checkbox
} from 'semantic-ui-react';

import { ShowServerError } from './Common';

class CDN extends React.Component {
  componentDidMount() {
    document.title = 'CDN';
  }

  componentWillUnmount() {
    this.dismounted = true;
  }

  render() {
    return (
      <Container textAlign="center">
        <Header as="h1">CDN</Header>
        <ProbeUrl {...this.props} />
        <ZoneConfig {...this.props} />
      </Container>
    );
  }
}

export default CDN;

class ProbeUrl extends React.PureComponent {
  state = {
    loading: false,
    result: null,
    serverError: null,
    url: '',
    purgeResult: null,
    purgeFSCache: true,
    deletedFSCacheFiles: null,
    purgeAllPages: true
  };

  componentDidMount() {
    const { location } = this.props;
    if (location.search) {
      const searchParams = new URLSearchParams(
        location.search.slice(1, location.search.length)
      );
      const url = searchParams.get('url') || '';
      if (url) {
        this.setState({ loading: true, url }, this.probeUrl);
      }
    }
  }

  probeUrl = async () => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    let response;
    let url = '/api/v0/cdn/probe';
    const formData = new FormData();
    formData.append('url', this.state.url);

    try {
      response = await fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
        }
      });
    } catch (ex) {
      return this.setState({ loading: false, serverError: ex });
    }

    if (this.dismounted) {
      return;
    }
    if (response.ok) {
      const result = await response.json();
      this.setState({
        loading: false,
        result,
        serverError: null
      });
    } else {
      this.setState({ loading: false, serverError: response });
    }
  };

  purgeUrl = async absoluteUrl => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    let response;
    let url = '/api/v0/cdn/purge';
    const formData = new FormData();
    formData.append('urls', absoluteUrl);
    if (this.state.purgeFSCache) {
      formData.append('fscache', true);
    }
    if (this.state.purgeAllPages) {
      if (this.state.result.other_pages) {
        this.state.result.other_pages.forEach(page => {
          formData.append('urls', page.url);
        });
      }
    }
    try {
      response = await fetch(url, {
        method: 'POST',
        body: formData,
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
        }
      });
    } catch (ex) {
      return this.setState({ loading: false, serverError: ex });
    }

    if (this.dismounted) {
      return;
    }
    if (response.ok) {
      const result = await response.json();
      this.setState({
        loading: false,
        purgeResult: result.purge,
        deletedFSCacheFiles: result.deleted,
        serverError: null
      });
    } else {
      this.setState({ loading: false, serverError: response });
    }
  };

  render() {
    const {
      loading,
      result,
      serverError,
      url,
      purgeResult,
      purgeFSCache,
      purgeAllPages,
      deletedFSCacheFiles
    } = this.state;
    return (
      <form
        onSubmit={event => {
          event.preventDefault();
          this.props.history.push({
            search: `?url=${encodeURI(this.state.url)}`
          });
          this.setState(
            {
              loading: true,
              purgeResult: null,
              deletedFSCacheFiles: null
            },
            () => {
              this.probeUrl();
            }
          );
        }}
      >
        <Header as="h2">URL Probe</Header>
        <Input
          action="Search"
          disabled={loading}
          fluid
          loading={loading}
          onChange={(event, data) => {
            this.setState({ url: data.value });
          }}
          placeholder="URL, oid, pattern"
          value={url}
        />
        <ShowServerError error={serverError} />
        {result && (
          <div style={{ marginTop: 20 }}>
            {result.other_pages && result.other_pages.length && (
              <Checkbox
                defaultChecked={purgeAllPages}
                toggle
                onChange={(event, data) => {
                  this.setState({ purgeAllPages: data.checked });
                }}
                label={`Purge all (${
                  result.other_pages.length
                }) other pages too`}
              />
            )}{' '}
            <Checkbox
              defaultChecked={purgeFSCache}
              toggle
              onChange={(event, data) => {
                this.setState({ purgeFSCache: data.checked });
              }}
              label="Purge FSCache too"
            />{' '}
            <Button
              primary
              loading={loading}
              disabled={loading}
              onClick={event => {
                event.preventDefault();
                this.setState(
                  {
                    loading: true,
                    purgeResult: null,
                    deletedFSCacheFiles: null
                  },
                  () => {
                    this.purgeUrl(result.absolute_url);
                  }
                );
              }}
            >
              Purge
            </Button>
            <Button
              primary
              loading={loading}
              disabled={loading}
              onClick={event => {
                event.preventDefault();
                this.setState(
                  {
                    loading: true,
                    result: null,
                    purgeResult: null,
                    deletedFSCacheFiles: null
                  },
                  this.probeUrl
                );
              }}
            >
              Probe Again
            </Button>{' '}
          </div>
        )}
        {purgeResult && (
          <div style={{ textAlign: 'left' }}>
            <h5>All URLs</h5>
            <ul>
              {purgeResult.all_urls.map(u => {
                return (
                  <li key={u}>
                    <code>{u}</code>
                  </li>
                );
              })}
            </ul>
            <pre>{JSON.stringify(purgeResult.result, null, 2)}</pre>
          </div>
        )}
        {deletedFSCacheFiles ? (
          <div style={{ textAlign: 'left' }}>
            <h4>Deleted FSCache Files</h4>
            {!deletedFSCacheFiles.length && <i>No FSCache files deleted</i>}
            <ul>
              {deletedFSCacheFiles.map(path => {
                return (
                  <li key={path}>
                    <code>{path}</code>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}

        {result && result.fscache && (
          <div style={{ textAlign: 'left' }}>
            <h4>FSCache Files</h4>

            {result.fscache.exists ? (
              <span>
                <code>{result.fscache.fspath}</code>{' '}
                <Icon name="check" color="green" title="Exists!" />
              </span>
            ) : (
              <span>
                Does not exist
                <Icon name="dont" color="orange" title="Doest not exist" />
              </span>
            )}
            {result.fscache.exists &&
            result.fscache.files &&
            result.fscache.files.length ? (
              <ul>
                {result.fscache.files.map(p => (
                  <li key={p}>
                    <code>{p}</code>
                  </li>
                ))}
              </ul>
            ) : (
              <i>No other files</i>
            )}
          </div>
        )}

        {result && result.other_pages && result.other_pages.length && (
          <div style={{ textAlign: 'left' }}>
            <h4>Other Pages ({result.other_pages.length})</h4>
            <ul>
              {result.other_pages.map(page => {
                return (
                  <li key={page.url}>
                    <a
                      href={`?url=${encodeURI(page.url)}`}
                      onClick={event => {
                        event.preventDefault();
                        this.setState(
                          {
                            url: page.url,
                            result: null,
                            loading: true
                          },
                          this.probeUrl
                        );
                      }}
                    >
                      {page.url}
                    </a>{' '}
                    {page.fspath_exists ? (
                      <Icon name="check" color="green" title="Exists!" />
                    ) : (
                      <Icon
                        name="dont"
                        color="orange"
                        title="Doest not exist"
                      />
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {result && <ShowProbeResult result={result} />}
      </form>
    );
  }
}

function ShowProbeResult({ result }) {
  return (
    <div style={{ marginTop: 20 }}>
      <Table basic="very" celled collapsing>
        <Table.Body>
          <Table.Row>
            <Table.Cell>
              <b>Absolute URL</b>
            </Table.Cell>
            <Table.Cell>
              <a href={result.absolute_url}>{result.absolute_url}</a>{' '}
              <a
                style={{ paddingLeft: 10 }}
                href={`https://tools.keycdn.com/performance?url=${encodeURI(
                  result.absolute_url
                )}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Icon name="external" /> KeyCDN Performance Test
              </a>
            </Table.Cell>
          </Table.Row>
          <Table.Row>
            <Table.Cell>
              <b>Status Code (HTTP/1.1)</b>
            </Table.Cell>
            <Table.Cell>
              <code>{result.http_1.status_code}</code>
              <small style={{ paddingLeft: 10 }}>
                (Took {(1000 * result.http_1.took).toFixed(1)}ms)
              </small>
            </Table.Cell>
          </Table.Row>
          {result.http_1.x_cache && (
            <Table.Row>
              <Table.Cell>
                <b>X-Cache (HTTP/1.1)</b>
              </Table.Cell>
              <Table.Cell>
                <code>{result.http_1.x_cache}</code>
              </Table.Cell>
            </Table.Row>
          )}
        </Table.Body>
      </Table>

      {result.http_1.headers && (
        <ShowHeaders title="HTTP/1.1" headers={result.http_1.headers} />
      )}
      {result.http_2.headers && (
        <ShowHeaders title="HTTP/2" headers={result.http_2.headers} />
      )}
    </div>
  );
}

function ShowHeaders({ title, headers }) {
  let keys = Object.keys(headers);
  keys.sort();

  function pretty(key, v) {
    return <code>{v}</code>;
  }
  return (
    <div style={{ marginTop: 20 }}>
      <Header as="h3">{title}</Header>
      <Table basic="very" celled collapsing>
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>Key</Table.HeaderCell>
            <Table.HeaderCell>Value</Table.HeaderCell>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {keys.map(key => {
            return (
              <Table.Row key={key}>
                <Table.Cell>
                  <b>{key}</b>
                </Table.Cell>
                <Table.Cell>{pretty(key, headers[key])}</Table.Cell>
              </Table.Row>
            );
          })}
        </Table.Body>
      </Table>
    </div>
  );
}

class ZoneConfig extends React.PureComponent {
  state = {
    config: null,
    loading: true,
    serverError: null
  };

  componentDidMount() {
    this.fetchZoneConfig();
  }

  fetchZoneConfig = async () => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    let response;
    let url = '/api/v0/cdn/config';
    try {
      response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
        }
      });
    } catch (ex) {
      return this.setState({ loading: false, serverError: ex });
    }

    if (this.dismounted) {
      return;
    }
    if (response.ok) {
      const result = await response.json();
      this.setState({
        loading: false,
        serverError: null,
        zoneConfig: result.data
      });
    } else {
      this.setState({ loading: false, serverError: response });
    }
  };
  render() {
    const { loading, serverError, zoneConfig } = this.state;
    return (
      <div style={{ marginTop: 50 }}>
        <Header as="h2">Zone Config</Header>
        <ShowServerError error={serverError} />
        {!serverError && loading && (
          <Container>
            <Loader
              active
              content="Loading..."
              inline="centered"
              size="massive"
              style={{ margin: '200px 0' }}
            />
          </Container>
        )}
        {zoneConfig && <ShowZoneConfig config={zoneConfig.zone} />}
      </div>
    );
  }
}

function ShowZoneConfig({ config }) {
  let keys = Object.keys(config);
  keys.sort();

  function pretty(v) {
    if (v === 'enabled') {
      return <Icon color="green" name="checkmark" />;
    } else if (v === 'disabled') {
      return <Icon color="red" name="dont" />;
    }
    return <code>{v}</code>;
  }
  return (
    <Table basic="very" celled collapsing>
      <Table.Header>
        <Table.Row>
          <Table.HeaderCell>Setting</Table.HeaderCell>
          <Table.HeaderCell>Value</Table.HeaderCell>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {keys.map(key => {
          return (
            <Table.Row key={key}>
              <Table.Cell>
                <b>{key}</b>
              </Table.Cell>
              <Table.Cell>{pretty(config[key])}</Table.Cell>
            </Table.Row>
          );
        })}
      </Table.Body>
    </Table>
  );
}
