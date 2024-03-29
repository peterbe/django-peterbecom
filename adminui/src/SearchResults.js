import React from 'react';
import {
  Checkbox,
  Divider,
  Header,
  Icon,
  Container,
  Loader,
  Statistic,
  Table,
  Input,
} from 'semantic-ui-react';

import { filterToQueryString, DisplayDate, ShowServerError } from './Common';

function defaultLoopSeconds(default_ = 60) {
  try {
    return parseInt(
      window.localStorage.getItem('searchresults-loopseconds') || default_,
      10
    );
  } catch (ex) {
    return default_;
  }
}

class SearchResults extends React.Component {
  state = {
    ongoing: null,
    loading: false,
    serverError: null,
    statistics: null,
    records: null,
    filters: null,
    loopSeconds: defaultLoopSeconds(),
  };

  componentDidMount() {
    document.title = 'Search Results';
    this.startLoop();
  }

  componentWillUnmount() {
    this.dismounted = true;
    if (this._loop) window.clearTimeout(this._loop);
  }

  fetchSearchResults = async () => {
    // if (!accessToken) {
    //   throw new Error('No accessToken');
    // }
    let response;
    let url = '/api/v0/searchresults/';
    if (this.state.filters) {
      url += `?${filterToQueryString(this.state.filters)}`;
    }
    try {
      response = await fetch(url, {
        // headers: {
        //   Authorization: `Bearer ${accessToken}`
        // }
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
        statistics: data.statistics,
        serverError: null,
      });
    } else {
      this.setState({ serverError: response });
    }
  };

  startLoop = () => {
    // this.fetchSearchResults(this.props.accessToken);
    this.fetchSearchResults();
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
    const { loading, serverError, statistics, records, filters } = this.state;

    return (
      <Container textAlign="center">
        <Header as="h1">Search Results</Header>
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

        {records && (
          <Records
            records={records}
            filters={filters}
            updateFilters={(filters) => {
              this.setState({ filters }, this.startLoop);
            }}
          />
        )}

        <Divider />
        {records && (
          <div>
            <Checkbox
              toggle
              defaultChecked={!!this.state.loopSeconds}
              onChange={(event) => {
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
                  onChange={(event) => {
                    const loopSeconds = parseInt(event.target.value);
                    if (loopSeconds > 0) {
                      this.setState({ loopSeconds }, () => {
                        window.localStorage.setItem(
                          'searchresults-loopseconds',
                          this.state.loopSeconds
                        );
                      });
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

export default SearchResults;

function equalArrays(array1, array2) {
  return (
    array1.length === array2.length &&
    array1.every((value, index) => value === array2[index])
  );
}

// XXX This is the same code (almost?) as that inside PostProcessing.
// Can we refactor to reuse?
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
  state = { differentIds: [], expanded: {} };
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

  renderSearchTimesListText = (times) => {
    return times
      .map(([key, seconds]) => {
        return `${key} in ${(seconds * 1000).toFixed(1)}ms`;
      })
      .join(', ');
  };
  render() {
    const { records, filters, updateFilters } = this.props;
    const { differentIds } = this.state;
    return (
      <form
        onSubmit={(event) => {
          event.preventDefault();
          updateFilters({ q: this.refs.q.inputRef.value });
        }}
      >
        <Table celled>
          <Table.Header>
            <Table.Row>
              <Table.HeaderCell>Q</Table.HeaderCell>
              <Table.HeaderCell>Found</Table.HeaderCell>
              <Table.HeaderCell>Date</Table.HeaderCell>
              <Table.HeaderCell>Notes</Table.HeaderCell>
            </Table.Row>
          </Table.Header>

          <Table.Body>
            {records.map((record) => {
              return (
                <Table.Row
                  key={record.id}
                  warning={differentIds.includes(record.id)}
                >
                  <Table.Cell>
                    <a
                      href={record._url}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={record.filepath}
                    >
                      {record.q}
                    </a>
                    {record.original_q && record.original_q !== record.q && (
                      <span>
                        (
                        <a
                          href={record._original_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          title={record.filepath}
                        >
                          {record.original_q}
                        </a>
                        )
                      </span>
                    )}{' '}
                    <Icon
                      color="grey"
                      size="small"
                      name={this.state.expanded[record.id] ? 'minus' : 'plus'}
                      onClick={(event) => {
                        event.preventDefault();
                        const expanded = Object.assign({}, this.state.expanded);
                        expanded[record.id] = !expanded[record.id];
                        this.setState({ expanded });
                      }}
                    />
                    {this.state.expanded[record.id] && (
                      <ShowSearchTerms terms={record.search_terms} />
                    )}
                  </Table.Cell>
                  <Table.Cell>
                    <b>{record.documents_found}</b> in{' '}
                    <b
                      title={this.renderSearchTimesListText(
                        record.search_times
                      )}
                    >
                      {(1000 * record.search_time).toFixed(1)}ms
                    </b>
                  </Table.Cell>
                  <Table.Cell>
                    <DisplayDate date={record.created} />
                  </Table.Cell>
                  <Table.Cell>
                    {(Object.keys(record.keywords).length && (
                      <span>
                        {Object.keys(record.keywords).map((k) => (
                          <span key={k}>
                            {k} = <code>{record.keywords[k]}</code>
                          </span>
                        ))}
                      </span>
                    )) ||
                      null}
                  </Table.Cell>
                </Table.Row>
              );
            })}
          </Table.Body>
        </Table>
        <Input
          ref="q"
          fluid
          defaultValue={(filters && filters.q) || ''}
          placeholder="Search filter..."
        />
      </form>
    );
  }
}

function ShowSearchTerms({ terms }) {
  return (
    <Table basic="very" celled collapsing compact>
      <Table.Header>
        <Table.Row>
          <Table.HeaderCell>Term</Table.HeaderCell>
          <Table.HeaderCell>Factor</Table.HeaderCell>
        </Table.Row>
      </Table.Header>

      <Table.Body>
        {terms.map(([factor, q]) => {
          //   let [factor, q] = each;
          factor = parseFloat(factor, 10);
          return (
            <Table.Row key={q}>
              <Table.Cell>
                <code>{q}</code>
              </Table.Cell>
              <Table.Cell>{factor.toFixed(2)}</Table.Cell>
            </Table.Row>
          );
        })}
      </Table.Body>
    </Table>
  );
}
