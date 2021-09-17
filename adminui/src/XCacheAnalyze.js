import React, { useCallback, useState, useEffect } from 'react';
import { Button, Flag, Header, Label, Table } from 'semantic-ui-react';

import { ShowServerError } from './Common';

function XCacheAnalyze({
  url,
  minimalButton = false,
  finished = null,
  start = false,
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);

  const startFetch = useCallback(async () => {
    let response;
    const formData = new FormData();
    formData.append('url', url);
    setLoading(true);
    try {
      response = await fetch('/api/v0/xcache/analyze', {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        throw new Error(`${response.status} on ${response.url}`);
      }
      setResults(await response.json());
    } catch (exc) {
      setError(exc);
    } finally {
      setLoading(false);
      if (finished) {
        finished(error);
      }
    }
  }, [error, finished, url]);

  useEffect(() => {
    if (start && !(loading || error || results)) {
      startFetch();
    }
  }, [start, loading, error, results, startFetch]);

  if (minimalButton && !(results || error)) {
    return (
      <Button loading={loading} onClick={startFetch} size="mini">
        {results || error ? 'Analyze again' : 'X-Cache Analyze'}
      </Button>
    );
  }
  return (
    <div style={{ marginTop: 10 }}>
      {results && <Header as="h3">X-Cache Analysis</Header>}
      {results && <XCacheResults results={results.xcache} />}
      <ShowServerError error={error} />
      <Button loading={loading} onClick={startFetch} primary>
        {results || error ? 'Analyze again' : 'X-Cache Analyze'}
      </Button>
    </div>
  );
}

export default XCacheAnalyze;

function XCacheResults({ results }) {
  function locationToName(loc) {
    const parsed = new URL(loc);
    const region = parsed.host.split('.');

    const map = {
      'us-east-2': ['Ohio (US)', 'us'],
      'us-east-1': ['N. Virginia (US)', 'us'],
      'us-west-1': ['N. California (US)', 'us'],
      'us-west-2': ['Oregon (US)', 'us'],
      'af-south-1': ['Cape Town (Africa)', 'za'],
      'ap-east-1': ['Hong Kong (Asia)', 'hk'],
      'ap-south-1': ['Mumbai (Asia)', 'in'],
      'ap-northeast-3': ['Osaka (Asia)', 'jp'],
      'ap-northeast-2': ['Seoul (Asia)', 'kr'],
      'ap-southeast-1': ['Singapore (Asia)', 'sg'],
      'ap-southeast-2': ['Sydney (Australia)', 'au'],
      'ap-northeast-1': ['Tokyo (Asia)', 'jp'],
      'ca-central-1': ['Canada', 'ca'],
      'cn-north-1': ['Beijing (Asia)', 'cn'],
      'cn-northwest-1': ['Ningxia (Asia)', 'cn'],
      'eu-central-1': ['Frankfurt (Europe)', 'de'],
      'eu-west-1': ['Ireland (Europe)', 'ie'],
      'eu-west-2': ['London (Europe)', 'gb'],
      'eu-south-1': ['Milan (Europe)', 'it'],
      'eu-west-3': ['Paris (Europe)', 'fr'],
      'eu-north-1': ['Stockholm (Europe)', 'se'],
      'me-south-1': ['Bahrain (Middle East)', 'bh'],
      'sa-east-1': ['São Paulo (South America)', 'br'],
    };
    if (!map[region[2]]) {
      return {
        name: 'Unknown',
        flag: null,
      };
    }
    return {
      name: map[region[2]][0],
      flag: map[region[2]][1],
    };
  }

  // Rearrange the 'results' so it's a list of tuples instead.
  const bundles = {};
  // Now the `:brotli` ones comes last
  const locationKeys = Object.keys(results).sort();
  for (const location of locationKeys) {
    const data = results[location];
    const locationPure = location.replace(':brotli', '');
    if (!(locationPure in bundles)) {
      bundles[locationPure] = [];
    }
    bundles[locationPure].push({
      brotli: location.includes(':brotli'),
      data,
    });
  }

  return (
    <Table basic="very" celled collapsing singleLine>
      <Table.Header>
        <Table.Row>
          <Table.HeaderCell>Location</Table.HeaderCell>
          <Table.HeaderCell>Gzip</Table.HeaderCell>
          <Table.HeaderCell>Brotli</Table.HeaderCell>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {Object.entries(bundles).map(([location, datum]) => {
          const locationDetails = locationToName(location);
          return (
            <Table.Row key={location}>
              <Table.Cell>
                {locationDetails && locationDetails.flag && (
                  <Flag
                    name={locationDetails.flag}
                    title={locationDetails.name}
                  />
                )}
                <b>{locationDetails.name}</b>
              </Table.Cell>
              {datum.map(({ data }, i) => {
                return (
                  <Table.Cell
                    key={`${location}:${i}`}
                    positive={!data.error && data.x_cache.includes('HIT')}
                    negative={!!data.error}
                    warning={!data.error && !data.x_cache.includes('HIT')}
                  >
                    {data.error && (
                      <Label as="span" color="red">
                        Error
                      </Label>
                    )}
                    {data.x_cache && !data.error && (
                      <Label
                        as="span"
                        color={data.x_cache.includes('HIT') ? 'green' : 'grey'}
                      >
                        {data.x_cache}
                      </Label>
                    )}{' '}
                    {!data.error && data.elapsed && (
                      <ShowSeconds seconds={data.elapsed} />
                    )}
                  </Table.Cell>
                );
              })}
            </Table.Row>
          );
        })}
      </Table.Body>
    </Table>
  );
}

function ShowSeconds({ seconds }) {
  if (seconds > 1) {
    return <b>{seconds.toFixed(1)}s</b>;
  } else {
    return <span>{(1000 * seconds).toFixed(1)}ms</span>;
  }
}
