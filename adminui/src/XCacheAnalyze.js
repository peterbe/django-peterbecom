import React from 'react';
import { Button, Flag, Header, Label, List, Table } from 'semantic-ui-react';

import { ShowServerError } from './Common';

class XCacheAnalyze extends React.PureComponent {
  state = {
    loading: false,
    results: null,
    serverError: null
  };

  componentDidUpdate(prevProps, prevState) {
    if (prevState.loading && !this.state.loading) {
      if (this.props.finished) {
        this.props.finished();
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
            Authorization: `Bearer ${this.props.accessToken}`
          }
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
        serverError: null
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
  const names = {
    defr: 'Frankfurt',
    uklo: 'London',
    usmi: 'Miami',
    usse: 'Seattle',
    ussf: 'San Francisco',
    frpa: 'Paris',
    nlam: 'Amsterdam',
    ausy: 'Sydney',
    usda: 'Dallas',
    usny: 'New York',
    cato: 'Toronto',
    jptk: 'Tokyo',
    inba: 'Bangalore',
    sgsg: 'Singapore'
  };
  return (
    <Table basic="very" celled collapsing>
      <Table.Body>
        {Object.entries(results).map(([location, data]) => {
          return (
            <Table.Row key={location}>
              <Table.Cell>
                <Flag name={location.slice(0, 2)} title={location} />
                <b>{names[location] ? names[location] : location}</b>
              </Table.Cell>
              <Table.Cell>
                {data.error && (
                  <Label as="span" color="red">
                    Error
                  </Label>
                )}
                {data['x-cache'] && !data.error && (
                  <Label
                    as="span"
                    color={data['x-cache'].includes('HIT') ? 'green' : 'grey'}
                  >
                    {data['x-cache']}
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
