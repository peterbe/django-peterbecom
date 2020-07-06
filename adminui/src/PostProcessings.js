import React, { useState, useEffect } from 'react';
import {
  Checkbox,
  Container,
  Divider,
  Header,
  Input,
  Loader,
  Message,
  Statistic,
  Table,
} from 'semantic-ui-react';
import useSWR from 'swr';

import {
  DisplayDate,
  equalArrays,
  filterToQueryString,
  ShowServerError,
} from './Common';

export default function PostProcessings({ accessToken }) {
  const [filters, setFilters] = useState(null);
  const baseFetchUrl = '/api/v0/postprocessings/';
  const [fetchUrl, setFetchUrl] = useState(baseFetchUrl);

  useEffect(() => {
    if (filters) {
      setFetchUrl(baseFetchUrl + `?${filterToQueryString(filters)}`);
    }
  }, [filters]);

  const { data, error: serverError } = useSWR(
    fetchUrl,
    async (url) => {
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      if (!response.ok) {
        throw new Error(`${response.status} on ${response.url}`);
      } else {
        return await response.json();
      }
    },
    {
      refreshInterval: 5000,
    }
  );

  const loading = !data && !serverError;

  return (
    <Container textAlign="center">
      <Header as="h1">Post Processings</Header>
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
      {data && data.statistics && <Statistics statistics={data.statistics} />}

      <Divider />
      {data && data.records && (
        <Records
          filters={filters}
          records={data.records}
          updateFilters={(filters) => {
            setFilters(filters);
          }}
        />
      )}
    </Container>
  );
}

class Statistics extends React.PureComponent {
  state = {
    differentKeys: [],
  };
  componentDidUpdate(prevProps, prevState) {
    if (equalArrays(prevState.differentKeys, this.state.differentKeys)) {
      const before = prevProps.statistics;
      const now = this.props.statistics;
      const differentKeys = [];
      now.groups.forEach((group, i) => {
        const otherGroup = before.groups[i];
        if (otherGroup) {
          group.items.forEach((item, j) => {
            if (item.value !== otherGroup.items[j].value) {
              differentKeys.push(group.key + item.key);
            }
          });
        }
      });
      if (!equalArrays(differentKeys, this.state.differentKeys)) {
        this.setState({ differentKeys });
      }
    }
  }
  render() {
    const { statistics } = this.props;
    let anyDifferent = false;

    return (
      <div>
        {statistics.groups.map((group) => {
          return (
            <div key={group.key}>
              <Header as="h3">{group.label}</Header>
              <Statistic.Group widths="four">
                {group.items.map((item) => {
                  const different = this.state.differentKeys.includes(
                    group.key + item.key
                  );
                  if (different) {
                    anyDifferent = true;
                  }
                  return (
                    <Statistic
                      color={different ? 'orange' : null}
                      key={item.key}
                    >
                      <Statistic.Value>{item.value}</Statistic.Value>
                      <Statistic.Label>{item.label}</Statistic.Label>
                    </Statistic>
                  );
                })}
              </Statistic.Group>
            </div>
          );
        })}

        {anyDifferent && (
          <p style={{ color: '#f2711c' }}>
            <small>Something changed!</small>
          </p>
        )}
      </div>
    );
  }
}

class Records extends React.PureComponent {
  state = {
    differentIds: [],
    search: (this.props.filters && this.props.filters.q) || '',
    exceptionsOnly: false,
  };

  componentDidUpdate(prevProps, prevState) {
    if (equalArrays(prevState.differentIds, this.state.differentIds)) {
      const before = prevProps.records.map((r) => r.id);
      const now = this.props.records.map((r) => r.id);
      const differentIds = now.filter((id) => !before.includes(id));
      if (!equalArrays(differentIds, this.state.differentIds)) {
        this.setState({ differentIds });
      }
    }
  }

  render() {
    const { records, updateFilters } = this.props;
    const { differentIds } = this.state;
    return (
      <form
        onSubmit={(event) => {
          event.preventDefault();
          updateFilters({ q: this.state.search });
        }}
      >
        <Table celled>
          <Table.Header>
            <Table.Row>
              <Table.HeaderCell>URL</Table.HeaderCell>
              <Table.HeaderCell>Duration</Table.HeaderCell>
              <Table.HeaderCell>Notes/Exception</Table.HeaderCell>
            </Table.Row>
          </Table.Header>

          <Table.Body>
            {records.map((record) => {
              return (
                <Table.Row
                  key={record.id}
                  negative={!!record.exception}
                  warning={differentIds.includes(record.id)}
                >
                  <Table.Cell>
                    <a
                      href={record.url}
                      rel="noopener noreferrer"
                      target="_blank"
                      title={record.filepath}
                    >
                      {new URL(record.url).pathname}
                    </a>{' '}
                    <a
                      href={`/cdn?url=${encodeURI(record.url)}`}
                      rel="noopener noreferrer"
                      target="_blank"
                      title="Do a CDN probe"
                    >
                      <small>(CDN probe)</small>
                    </a>
                    <br />
                    <DisplayDate date={record.created} />
                    {record._previous && (
                      <span>
                        {' '}
                        (last time was:{' '}
                        <DisplayDate date={record._previous.created} />)
                      </span>
                    )}
                  </Table.Cell>
                  <Table.Cell>
                    {record.duration ? `${record.duration.toFixed(1)}s` : 'n/a'}
                  </Table.Cell>
                  <Table.Cell>
                    {record.exception && record._latest && (
                      <Message warning>
                        <p>
                          <b>Note!</b> A more recent, successful, post
                          processing exists.
                        </p>
                        <p>
                          Last one was{' '}
                          <b>
                            <DisplayDate date={record._latest.created} />
                          </b>
                        </p>
                      </Message>
                    )}
                    {record.exception ? (
                      <pre className="exception">{record.exception}</pre>
                    ) : null}

                    <ol style={{ margin: 0 }}>
                      {record.notes.map((note, i) => {
                        return <li key={i}>{note}</li>;
                      })}
                    </ol>
                  </Table.Cell>
                </Table.Row>
              );
            })}
          </Table.Body>
        </Table>
        <div style={{ textAlign: 'left' }}>
          <Input
            fluid
            placeholder="Search filter..."
            value={this.state.search}
            action="Search"
            onChange={(event, data) => {
              const search = data.value;
              this.setState({ search });
            }}
          />
          <Checkbox
            toggle
            defaultChecked={this.state.exceptionsOnly}
            onChange={(event, data) => {
              this.setState({ exceptionsOnly: data.checked }, () => {
                updateFilters({
                  q: this.state.search,
                  exceptions: this.state.exceptionsOnly,
                });
              });
            }}
            label="Exceptions only"
          />
        </div>
      </form>
    );
  }
}
