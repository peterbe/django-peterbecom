import React from 'react';
import {
  Checkbox,
  Divider,
  Header,
  Container,
  Loader,
  Statistic,
  Table,
  Input
} from 'semantic-ui-react';

import { DisplayDate, ShowServerError } from './Common';

class PostProcessings extends React.Component {
  state = {
    ongoing: null,
    loading: false,
    serverError: null,
    statistics: null,
    records: null,
    loopSeconds: null
  };

  componentDidMount() {
    document.title = 'Post Processing';
    this.fetchPostProcessings(this.props.accessToken);
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
    try {
      response = await fetch('/api/v0/postprocessings/', {
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
        statistics: data.statistics,
        records: data.records,
        serverError: null
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
      }, this.state.loopSeconds * 1000);
    }
  };

  render() {
    const { loading, serverError, statistics, records } = this.state;

    return (
      <Container textAlign="center">
        <Header as="h1">Post Processings</Header>
        <ShowServerError error={this.state.serverError} />
        {!serverError && loading && (
          <Container>
            <Loader
              active
              size="massive"
              inline="centered"
              content="Loading..."
              style={{ margin: '200px 0' }}
            />
          </Container>
        )}
        {statistics && <Statistics statistics={statistics} />}

        <Divider />
        {records && <Records records={records} />}

        <Divider />
        {(statistics || records) && (
          <div>
            <Checkbox
              toggle
              onChange={event => {
                if (!this.state.loopSeconds) {
                  this.setState({ loopSeconds: 10 }, () => {
                    this.startLoop();
                  });
                } else {
                  this.setState({ loopSeconds: null });
                }
              }}
            />
            {this.state.loopSeconds && (
              <div>
                Every{' '}
                <Input
                  type="number"
                  size="small"
                  onChange={event => {
                    const loopSeconds = parseInt(event.target.value);
                    if (loopSeconds > 0) {
                      this.setState({ loopSeconds });
                    }
                  }}
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

function equalArrays(array1, array2) {
  return (
    array1.length === array2.length &&
    array1.every((value, index) => value === array2[index])
  );
}

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
    const { records } = this.props;
    const { differentIds } = this.state;
    return (
      <Table celled>
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>URL</Table.HeaderCell>
            <Table.HeaderCell>Duration</Table.HeaderCell>
            <Table.HeaderCell>Exception</Table.HeaderCell>
            <Table.HeaderCell>Notes</Table.HeaderCell>
          </Table.Row>
        </Table.Header>

        <Table.Body>
          {records.map(record => {
            return (
              <Table.Row
                key={record.id}
                negative={record.exception}
                warning={differentIds.includes(record.id)}
              >
                <Table.Cell>
                  <a
                    href={record.url}
                    target="_blank"
                    rel="noopener noreferrer"
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
                  {record.exception ? <pre>{record.exception}</pre> : null}
                </Table.Cell>
                <Table.Cell>
                  <ul style={{ margin: 0 }}>
                    {record.notes.map((note, i) => {
                      return <li key={i}>{note}</li>;
                    })}
                  </ul>
                </Table.Cell>
              </Table.Row>
            );
          })}
        </Table.Body>
      </Table>
    );
  }
}
