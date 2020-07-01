import React from 'react';
import { Button, Flag, Header, Label, List, Table } from 'semantic-ui-react';

import { ShowServerError } from './Common';

class XCacheAnalyze extends React.PureComponent {
  state = {
    loading: false,
    results: null,
    serverError: null,
  };

  componentDidUpdate(prevProps, prevState) {
    if (prevState.loading && !this.state.loading) {
      if (this.props.finished) {
        this.props.finished(this.state.serverError);
      }
    }
    if (!prevProps.start && this.props.start && !this.state.loading) {
      this.start();
    }
  }

  start = () => {
    this.setState({ loading: true, serverError: null }, async () => {
      const formData = new FormData();
      formData.append('url', this.props.url);

      let response;
      try {
        response = await fetch('/api/v0/xcache/analyze', {
          method: 'POST',
          body: formData,
          headers: {
            Authorization: `Bearer ${this.props.accessToken}`,
          },
        });
      } catch (ex) {
        return this.setState({ loading: false, serverError: ex });
      }
      if (!response.ok) {
        return this.setState({ loading: false, serverError: response });
      }
      const results = await response.json();
      this.setState({
        loading: false,
        results,
        serverError: null,
      });
    });
  };

  render() {
    const { loading, results, serverError } = this.state;
    const { minimalButton = false } = this.props;
    if (minimalButton && !(results || serverError)) {
      return (
        <Button loading={loading} onClick={this.start} size="mini">
          {results || serverError ? 'Analyze again' : 'X-Cache Analyze'}
        </Button>
      );
    }
    return (
      <div style={{ marginTop: 20 }}>
        {results && <Header as="h2">X-Cache Analysis</Header>}
        {results && <XCacheResults results={results.xcache} />}
        <ShowServerError error={serverError} />
        <Button loading={loading} onClick={this.start} primary>
          {results || serverError ? 'Analyze again' : 'X-Cache Analyze'}
        </Button>
      </div>
    );
  }
}

export default XCacheAnalyze;

function XCacheResults({ results }) {
  function locationToName(loc) {
    let isBrotli = false;
    if (loc.endsWith(':brotli')) {
      isBrotli = true;
      loc = loc.replace(':brotli', '');
    }

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
        isBrotli,
      };
    }
    return {
      name: map[region[2]][0],
      flag: map[region[2]][1],
      isBrotli,
    };
  }

  return (
    <Table basic="very" celled collapsing singleLine>
      <Table.Body>
        {Object.entries(results).map(([location, data]) => {
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
                <b>{locationDetails.name}</b>{' '}
                {locationDetails.isBrotli && <i>Brotli</i>}
              </Table.Cell>
              <Table.Cell
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
                )}
              </Table.Cell>
              <Table.Cell>
                {data.ttfb && (
                  <List.Description>{data.ttfb.toFixed(1)}ms</List.Description>
                )}
              </Table.Cell>
            </Table.Row>
          );
        })}
      </Table.Body>
    </Table>
  );
}
