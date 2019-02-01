import React from 'react';
import {
  Checkbox,
  Container,
  Header,
  Input,
  Label,
  Loader,
  Table
} from 'semantic-ui-react';

import {
  DisplayDate,
  equalArrays,
  filterToQueryString,
  ShowServerError
} from './Common';
import { BASE_URL } from './Config';

function defaultLoopSeconds(default_ = 10) {
  try {
    return parseInt(
      window.localStorage.getItem('realtimehits-loopseconds') || default_,
      10
    );
  } catch (ex) {
    return default_;
  }
}

class RealtimeBlogitemHits extends React.Component {
  state = {
    filters: null,
    grouped: null,
    hits: [],
    lastAddDate: null,
    loading: true,
    loopSeconds: defaultLoopSeconds(),
    ongoing: null,
    serverError: null
  };

  componentDidMount() {
    document.title = 'Blogitem Realtime Hits';
    this.startLoop();
  }

  componentWillUnmount() {
    this.dismounted = true;
    if (this._loop) window.clearTimeout(this._loop);
  }

  startLoop = () => {
    this.fetchHits();
    if (this._loop) {
      window.clearTimeout(this._loop);
    }
    if (this.state.loopSeconds) {
      this._loop = window.setTimeout(() => {
        this.startLoop();
      }, 1000 * this.state.loopSeconds);
    }
  };

  fetchHits = async () => {
    if (!this.props.accessToken) {
      throw new Error('No accessToken');
    }
    let response;
    let url = '/api/v0/plog/realtimehits/?';
    if (this.state.lastAddDate) {
      url += `since=${encodeURIComponent(this.state.lastAddDate)}`;
    }
    if (this.state.filters) {
      url += `&${filterToQueryString(this.state.filters)}`;
    }
    try {
      response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${this.props.accessToken}`
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
      const hits = this.state.hits.concat(data.hits);

      this.setState({
        grouped: this._groupHits(hits),
        hits,
        lastAddDate: data.last_add_date || this.state.lastAddDate,
        loading: false,
        serverError: null
      });
    } else {
      this.setState({ serverError: response });
    }
  };

  _groupHits = hits => {
    const byOids = {};
    hits.forEach(hit => {
      if (!byOids[hit.blogitem.oid]) {
        byOids[hit.blogitem.oid] = {
          blogitem: hit.blogitem,
          count: 0,
          date: hit.add_date
          // http_referers: {}
        };
      }
      byOids[hit.blogitem.oid].count++;
      if (hit.add_date > byOids[hit.blogitem.oid].date) {
        byOids[hit.blogitem.oid].date = hit.add_date;
      }
      // if ()
    });
    return Object.values(byOids)
      .sort((a, b) => {
        if (a.count === b.count) {
          return a.date < b.date ? 1 : -1;
        }
        return b.count - a.count;
      })
      .slice(0, 30);
  };

  updateFilters = filters => {
    this.setState(
      { filters, grouped: null, hits: [], lastAddDate: null },
      this.startLoop
    );
  };

  render() {
    const { filters, grouped, loading, serverError } = this.state;

    return (
      <Container textAlign="center">
        <Header as="h1">Blogitem Realtime Hits</Header>
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

        {grouped && (
          <Hits
            filters={filters}
            grouped={grouped}
            updateFilters={this.updateFilters}
          />
        )}
        {grouped && (
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

export default RealtimeBlogitemHits;

class Hits extends React.PureComponent {
  state = { differentIds: [] };
  componentDidUpdate(prevProps, prevState) {
    if (equalArrays(prevState.differentIds, this.state.differentIds)) {
      const before = prevProps.grouped.map(r => r.blogitem.id);
      const now = this.props.grouped.map(r => r.blogitem.id);
      const differentIds = now.filter(id => !before.includes(id));
      if (!equalArrays(differentIds, this.state.differentIds)) {
        this.setState({ differentIds });
      }
    }
  }
  render() {
    const { filters, grouped, updateFilters } = this.props;
    const { differentIds } = this.state;
    return (
      <form
        onSubmit={event => {
          event.preventDefault();
          updateFilters({ search: this.refs.q.inputRef.value });
        }}
      >
        <Input
          defaultValue={(filters && filters.search) || ''}
          fluid
          placeholder="Search filter..."
          ref="q"
        />
        <Table celled className="hits">
          <Table.Header>
            <Table.Row>
              <Table.HeaderCell>Title</Table.HeaderCell>
              <Table.HeaderCell>Count</Table.HeaderCell>
            </Table.Row>
          </Table.Header>

          <Table.Body>
            {grouped.map(record => {
              return (
                <Table.Row
                  key={record.blogitem.oid}
                  warning={differentIds.includes(record.blogitem.id)}
                >
                  <Table.Cell>
                    <a
                      href={BASE_URL + record.blogitem._absolute_url}
                      rel="noopener noreferrer"
                      target="_blank"
                      title={record.blogitem.oid}
                    >
                      {record.blogitem.title}
                    </a>{' '}
                    <Label
                      color={!record.blogitem._is_published ? 'orange' : null}
                      size="tiny"
                    >
                      Published <DisplayDate date={record.blogitem.pub_date} />
                    </Label>
                  </Table.Cell>
                  <Table.Cell>{record.count.toLocaleString()}</Table.Cell>
                </Table.Row>
              );
            })}
          </Table.Body>
        </Table>
      </form>
    );
  }
}
