import React from 'react';
import {
  Checkbox,
  Container,
  Divider,
  Header,
  Input,
  Loader,
  Statistic,
  Table
} from 'semantic-ui-react';

import {
  DisplayDate,
  equalArrays,
  filterToQueryString,
  ShowServerError
} from './Common';

function defaultLoopSeconds(default_ = 10) {
  try {
    return parseInt(
      window.localStorage.getItem('postprocess-loopseconds') || default_,
      10
    );
  } catch (ex) {
    return default_;
  }
}

class PostProcessings extends React.Component {
  state = {
    filters: null,
    loading: false,
    loopSeconds: defaultLoopSeconds(),
    ongoing: null,
    records: null,
    serverError: null,
    statistics: null
  };

  componentDidMount() {
    document.title = 'Post Processing';
    this.startLoop();
  }

  componentWillUnmount() {
    this.dismounted = true;
    if (this._loop) window.clearTimeout(this._loop);
  }

  fetchPostProcessings = async accessToken => {
    if (!accessToken) {
      throw new Error('No accessToken');
    }
    let response;
    let url = '/api/v0/postprocessings/';
    if (this.state.filters) {
      url += `?${filterToQueryString(this.state.filters)}`;
    }
    try {
      response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${accessToken}`
        }
      });
    } catch (ex) {
      return this.setState({ serverError: ex });
    }

    if (this.dismounted) {
      return;
    }
    if (response.ok) {
      const data = await response.json();
      this.setState({
        records: data.records,
        serverError: null,
        statistics: data.statistics
      });
    } else {
      this.setState({ serverError: response });
    }
  };

  startLoop = () => {
    this.fetchPostProcessings(this.props.accessToken);
    if (this._loop) {
      window.clearTimeout(this._loop);
    }
    if (this.state.loopSeconds) {
      this._loop = window.setTimeout(() => {
        this.startLoop();
      }, 1000 * this.state.loopSeconds);
    }
  };

  render() {
    const { filters, loading, records, serverError, statistics } = this.state;

    return (
      <Container textAlign="center">
        <Header as="h1">Post Processings</Header>
        <ShowServerError error={this.state.serverError} />
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
        {statistics && <Statistics statistics={statistics} />}

        <Divider />
        {records && (
          <Records
            filters={filters}
            records={records}
            updateFilters={filters => {
              this.setState({ filters }, this.startLoop);
            }}
          />
        )}

        <Divider />
        {(statistics || records) && (
          <div>
            <Checkbox
              defaultChecked={!!this.state.loopSeconds}
              onChange={event => {
                if (!this.state.loopSeconds) {
                  this.setState({ loopSeconds: 10 }, () => {
                    this.startLoop();
                  });
                } else {
                  this.setState({ loopSeconds: null });
                }
              }}
              toggle
            />
            {this.state.loopSeconds && (
              <div>
                Every{' '}
                <Input
                  onChange={event => {
                    const loopSeconds = parseInt(event.target.value);
                    if (loopSeconds > 0) {
                      this.setState({ loopSeconds }, () => {
                        window.localStorage.setItem(
                          'postprocess-loopseconds',
                          this.state.loopSeconds
                        );
                      });
                    }
                  }}
                  size="small"
                  type="number"
                  value={this.state.loopSeconds}
                />{' '}
                seconds.
              </div>
            )}
          </div>
        )}
      </Container>
    );
  }
}

export default PostProcessings;

class Statistics extends React.PureComponent {
  state = {
    differentKeys: []
  };
  componentDidUpdate(prevProps, prevState) {
    if (equalArrays(prevState.differentKeys, this.state.differentKeys)) {
      const before = prevProps.statistics;
      const now = this.props.statistics;
      const differentKeys = [];
      now.groups.forEach((group, i) => {
        const otherGroup = before.groups[i];
        group.items.forEach((item, j) => {
          if (item.value !== otherGroup.items[j].value) {
            differentKeys.push(group.key + item.key);
          }
        });
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
        {statistics.groups.map(group => {
          return (
            <div key={group.key}>
              <Header as="h3">{group.label}</Header>
              <Statistic.Group widths="four">
                {group.items.map(item => {
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
  state = { differentIds: [] };
  componentDidUpdate(prevProps, prevState) {
    if (equalArrays(prevState.differentIds, this.state.differentIds)) {
      const before = prevProps.records.map(r => r.id);
      const now = this.props.records.map(r => r.id);
      const differentIds = now.filter(id => !before.includes(id));
      if (!equalArrays(differentIds, this.state.differentIds)) {
        this.setState({ differentIds });
      }
    }
  }
  render() {
    const { filters, records, updateFilters } = this.props;
    const { differentIds } = this.state;
    return (
      <form
        onSubmit={event => {
          event.preventDefault();
          updateFilters({ q: this.refs.q.inputRef.value });
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
            {records.map(record => {
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
        <Input
          defaultValue={(filters && filters.q) || ''}
          fluid
          placeholder="Search filter..."
          ref="q"
        />
      </form>
    );
  }
}
