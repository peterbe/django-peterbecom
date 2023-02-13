import React, { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Checkbox,
  Container,
  Header,
  Icon,
  Input,
  Loader,
  Message,
  Table,
} from 'semantic-ui-react';
import useSWR, { mutate } from 'swr';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { toast } from 'react-semantic-toasts';

import { DisplayDate, ShowServerError } from './Common';
import XCacheAnalyze from './XCacheAnalyze';

async function basicFetch(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${response.status} on ${url}`);
  }
  return await response.json();
}

class CDN extends React.Component {
  componentDidMount() {
    document.title = 'CDN';
  }

  render() {
    return (
      <Container textAlign="center">
        <Header as="h1">CDN</Header>
        <ProbeUrl {...this.props} />
        <CDNCheck {...this.props} />
        <PurgeURLs {...this.props} />
      </Container>
    );
  }
}

export default function CDNOuter() {
  const location = useLocation();
  return <CDN location={location} />;
}

function CDNCheck() {
  const [showConfig, setShowConfig] = useState(false);
  const { data: result, error: serverError } = useSWR(
    '/api/v0/cdn/check',
    basicFetch
  );
  const loading = !result && !serverError;
  return (
    <>
      <div style={{ marginTop: 50 }}>
        <Header as="h3">CDN Check</Header>
        <ShowServerError error={serverError} />
        {loading && <i>Loading CDN Check...</i>}
        {!loading && result && (
          <Message
            negative={!result.checked}
            size="tiny"
            success={!!result.checked}
          >
            {result.checked
              ? `CDN Looks fine (${result.checked})`
              : 'CDN Check failed!'}
          </Message>
        )}
      </div>

      {!loading && result && result.checked && (
        <p style={{ marginTop: 10 }}>
          <Button
            onClick={() => {
              setShowConfig((prevState) => !prevState);
            }}
          >
            {showConfig ? 'Hide Full Zone Config' : 'Display Full Zone Config'}
          </Button>
        </p>
      )}
      {!loading && showConfig && result && result.checked && <ZoneConfig />}
    </>
  );
}

function ProbeUrl() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [url, setURL] = useState(searchParams.get('url') || '');
  const [purgeAllPages, setPurgeAllPages] = useState(true);
  const [purgeFSCache, setPurgeFSCache] = useState(true);
  const [purgeURL, setPurgeURL] = useState(null);

  const probeURL = useMemo(() => {
    if (!searchParams.get('url')) return null;
    return '/api/v0/cdn/probe?' + searchParams.toString();
  }, [searchParams]);

  const { data: probeResult, error: probeError } = useSWR(
    probeURL,
    async (url) => {
      const formData = new FormData();
      formData.append('url', searchParams.get('url'));
      const response = await fetch(url, { method: 'POST', body: formData });
      if (!response.ok) {
        throw new Error(`${response.status} on ${url}`);
      }
      return await response.json();
    }
  );

  useEffect(() => {
    setPurgeURL(null);
  }, [probeURL]);

  const { data: purgeResult, error: purgeError } = useSWR(
    purgeURL ? '/api/v0/cdn/purge' : null,
    async (url) => {
      const formData = new FormData();
      formData.append('urls', purgeURL);
      if (purgeFSCache) {
        formData.append('fscache', true);
      }
      if (purgeAllPages && probeResult.other_pages) {
        for (const page of probeResult.other_pages) {
          formData.append('urls', page.url);
        }
      }
      const response = await fetch(url, { method: 'POST', body: formData });
      if (!response.ok) {
        throw new Error(`${response.status} on ${url}`);
      }
      return await response.json();
    },
    {
      revalidateOnFocus: false,
    }
  );

  const loading = Boolean(
    searchParams.get('url') && !probeResult && !probeError
  );
  const deletedFSCacheFiles = null;
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        setSearchParams({ url: url.trim() });
      }}
    >
      <Header as="h2">URL Probe</Header>
      <Input
        action="Search"
        disabled={loading}
        fluid
        loading={loading}
        onChange={(event, data) => {
          setURL(data.value);
        }}
        placeholder="URL, oid, pattern"
        value={url}
      />
      <ShowServerError error={probeError} />
      <ShowServerError error={purgeError} />
      {probeResult && (
        <div style={{ marginTop: 20 }}>
          {probeResult.other_pages && probeResult.other_pages.length && (
            <Checkbox
              defaultChecked={purgeAllPages}
              label={`Purge all (${probeResult.other_pages.length}) other pages too`}
              onChange={(event, data) => {
                setPurgeAllPages(data.checked);
              }}
              toggle
            />
          )}{' '}
          <Checkbox
            defaultChecked={purgeFSCache}
            label="Purge FSCache too"
            onChange={(event, data) => {
              setPurgeFSCache(data.checked);
            }}
            toggle
          />{' '}
          <Button
            disabled={loading}
            loading={loading}
            onClick={(event) => {
              event.preventDefault();
              setPurgeURL(probeResult.absolute_url);
            }}
            primary
          >
            Purge
          </Button>
          <Button
            disabled={loading}
            loading={loading}
            onClick={(event) => {
              event.preventDefault();
              mutate(probeURL);
            }}
            primary
          >
            Probe Again
          </Button>{' '}
        </div>
      )}
      {purgeResult && (
        <div style={{ textAlign: 'left' }}>
          <h5>All URLs</h5>
          <ul>
            {purgeResult.purge.all_urls.map((u) => {
              return (
                <li key={u}>
                  <code>{u}</code>
                </li>
              );
            })}
          </ul>
          <pre>{JSON.stringify(purgeResult.purge.results, null, 2)}</pre>
        </div>
      )}
      {deletedFSCacheFiles ? (
        <div style={{ textAlign: 'left' }}>
          <h4>Deleted FSCache Files</h4>
          {!deletedFSCacheFiles.length && <i>No FSCache files deleted</i>}
          <ul>
            {deletedFSCacheFiles.map((path) => {
              return (
                <li key={path}>
                  <code>{path}</code>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {probeResult &&
        probeResult.other_pages &&
        probeResult.other_pages.length && (
          <div style={{ textAlign: 'left' }}>
            <h4>Other Pages ({probeResult.other_pages.length})</h4>
            <ul>
              {probeResult.other_pages.map((page) => {
                return (
                  <li key={page.url}>
                    <Link
                      to={`?url=${encodeURI(page.url)}`}
                      onClick={(event) => {
                        event.preventDefault();
                        setSearchParams({ url: page.url });
                        setURL(page.url);
                      }}
                    >
                      {page.url}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

      {probeResult && <ShowProbeResult result={probeResult} />}
      {probeResult && <XCacheAnalyze url={probeResult.absolute_url} />}
    </form>
  );
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
                href={`https://tools.keycdn.com/performance?url=${encodeURI(
                  result.absolute_url
                )}`}
                rel="noopener noreferrer"
                style={{ paddingLeft: 10 }}
                target="_blank"
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
        <ShowHeaders headers={result.http_1.headers} title="HTTP/1.1" />
      )}
      {result.http_2.headers && (
        <ShowHeaders headers={result.http_2.headers} title="HTTP/2" />
      )}
    </div>
  );
}

function ShowHeaders({ headers, title }) {
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
          {keys.map((key) => {
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

function ZoneConfig() {
  const { data, error: serverError } = useSWR('/api/v0/cdn/config', basicFetch);
  const loading = !data && !serverError;
  const zoneConfig = data ? data.data : null;
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
        {keys.map((key) => {
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

function PurgeURLs() {
  const [refreshInterval] = useState(10000);
  const { data, error: serverError } = useSWR(
    '/api/v0/cdn/purge/urls',
    basicFetch,
    {
      refreshInterval,
    }
  );

  useEffect(() => {
    if (serverError) {
      toast({
        type: 'error',
        title: 'CDN Purge URLs Error',
        description: serverError.toString(),
        time: 7000,
      });
    }
  }, [serverError]);

  const loading = !data && !serverError;

  if (loading) {
    return (
      <p>
        <i>Loading Purge CDN URLs</i>
      </p>
    );
  }

  const { queued, recent } = data;

  return (
    <div style={{ marginTop: 50 }}>
      <Header as="h2">Purge URLs</Header>
      <ShowServerError error={serverError} />
      <Header as="h3">Queued URLs ({queued.length})</Header>
      <Table celled>
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>URL</Table.HeaderCell>
            <Table.HeaderCell>Attempts</Table.HeaderCell>
            <Table.HeaderCell>Date</Table.HeaderCell>
          </Table.Row>
        </Table.Header>

        <Table.Body>
          {queued.map((record) => {
            return (
              <Table.Row
                key={record.id}
                negative={!!record.exception}
                warning={!!record.attempts}
              >
                <Table.Cell>
                  <code>{record.url}</code>
                  {record.exception && <pre>{record.exception}</pre>}
                </Table.Cell>
                <Table.Cell>{record.attempts}</Table.Cell>
                <Table.Cell>
                  <DisplayDate date={record.created} />{' '}
                  {record.attempted && <DisplayDate date={record.attempted} />}
                </Table.Cell>
              </Table.Row>
            );
          })}
        </Table.Body>
      </Table>
      <Header as="h3">Recent URLs</Header>
      <Table celled>
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>URL</Table.HeaderCell>
            <Table.HeaderCell>
              <abbr title="Attempts">A</abbr>
            </Table.HeaderCell>
            <Table.HeaderCell>Processed</Table.HeaderCell>
          </Table.Row>
        </Table.Header>

        <Table.Body>
          {recent.map((record) => {
            return (
              <Table.Row key={record.id} warning={!!record.cancelled}>
                <Table.Cell>
                  <a href={record.url}>{record.url}</a>
                </Table.Cell>
                <Table.Cell>{record.attempts}</Table.Cell>
                <Table.Cell>
                  {record.cancelled ? 'cancelled ' : 'processed '}
                  <DisplayDate
                    date={
                      record.cancelled ? record.cancelled : record.processed
                    }
                  />{' '}
                  (
                  <DisplayDate
                    date={
                      record.cancelled ? record.cancelled : record.processed
                    }
                    now={record.created}
                    prefix="took"
                  />
                  )
                </Table.Cell>
              </Table.Row>
            );
          })}
        </Table.Body>
      </Table>
    </div>
  );
}
