import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import useSWR from 'swr';
import {
  Checkbox,
  Container,
  Header,
  Input,
  Label,
  Loader,
  Table,
} from 'semantic-ui-react';

import { DisplayDate, ShowServerError, usePrevious } from './Common';

const LOCALSTORAGE_KEY = 'realtimehits-loopseconds';
function defaultLoopSeconds(default_ = 10) {
  try {
    return parseInt(
      window.localStorage.getItem(LOCALSTORAGE_KEY) || default_,
      10
    );
  } catch (ex) {
    return default_;
  }
}

export default function RealtimeBlogitemHits() {
  const [loopSeconds, setLoopSeconds] = useState(defaultLoopSeconds());
  const [hits, setHits] = useState([]);
  const [filters, setFilters] = useState(null);
  const previousFilters = usePrevious(filters);
  const [lastAddDate, setLastAddDate] = useState(null);
  useEffect(() => {
    if (
      (filters && !previousFilters) ||
      JSON.stringify(filters) !== JSON.stringify(previousFilters)
    ) {
      setHits([]);
      setLastAddDate(null);
    }
  }, [filters, previousFilters]);

  const apiURL = useMemo(() => {
    let url = '/api/v0/plog/realtimehits/';
    const sp = new URLSearchParams(filters ? filters : {});
    if (lastAddDate) {
      sp.set('since', lastAddDate);
    }
    return `${url}?${sp.toString()}`;
  }, [lastAddDate, filters]);

  const { data, error: serverError } = useSWR(
    apiURL,
    async (url) => {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`${response.status} on ${url}`);
      }
      const data = await response.json();
      return data;
    },
    {
      dedupingInterval: 1000,
      refreshInterval: loopSeconds * 1000,
    }
  );

  useEffect(() => {
    if (data && data.last_add_date) {
      setLastAddDate(data.last_add_date);
    }
  }, [data]);
  useEffect(() => {
    if (data) {
      setHits((prevState) => {
        return [...prevState, ...data.hits];
      });
    }
  }, [data]);

  useEffect(() => {
    if (loopSeconds >= 0) {
      window.localStorage.setItem(LOCALSTORAGE_KEY, loopSeconds);
    }
  }, [loopSeconds]);

  const loading = !hits.length && !data && !serverError;
  const grouped = groupHits(hits);

  return (
    <Container textAlign="center">
      <Header as="h1">Blogitem Realtime Hits</Header>
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

      {Object.keys(grouped).length > 0 && (
        <Hits
          filters={filters}
          grouped={grouped}
          loading={loading}
          updateFilters={(newFilters) => {
            setFilters((prevState) => {
              return Object.assign({}, prevState ? prevState : {}, newFilters);
            });
          }}
        />
      )}
      {Object.keys(grouped).length > 0 && (
        <div>
          <Checkbox
            defaultChecked={!!loopSeconds}
            onChange={() => {
              if (!loopSeconds) {
                setLoopSeconds(10);
              } else {
                setLoopSeconds(0);
              }
            }}
            toggle
          />
          {loopSeconds > 0 && (
            <div>
              Every{' '}
              <Input
                onChange={(event) => {
                  setLoopSeconds(parseInt(event.target.value));
                }}
                size="small"
                type="number"
                value={loopSeconds}
              />{' '}
              seconds.
            </div>
          )}
        </div>
      )}
    </Container>
  );
}

function groupHits(hits) {
  const byOids = {};
  hits.forEach((hit) => {
    if (!byOids[hit.blogitem.oid]) {
      byOids[hit.blogitem.oid] = {
        blogitem: hit.blogitem,
        count: 0,
        date: hit.add_date,
        // http_referers: {}
      };
    }
    byOids[hit.blogitem.oid].count++;
    if (hit.add_date > byOids[hit.blogitem.oid].date) {
      byOids[hit.blogitem.oid].date = hit.add_date;
    }
  });
  return Object.values(byOids)
    .sort((a, b) => {
      if (a.count === b.count) {
        return a.date < b.date ? 1 : -1;
      }
      return b.count - a.count;
    })
    .slice(0, 30);
}

function Hits({ filters, loading, grouped, updateFilters }) {
  const [search, setSearch] = useState(
    filters && filters.search ? filters.search : ''
  );
  const previousGrouped = usePrevious(grouped);
  let differentIds = [];
  if (previousGrouped) {
    const before = previousGrouped.map((r) => r.blogitem.id);
    const now = grouped.map((r) => r.blogitem.id);
    differentIds = now.filter((id) => !before.includes(id));
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        updateFilters({ search });
      }}
    >
      <Input
        fluid
        placeholder="Search filter..."
        value={search}
        loading={loading}
        action="Search"
        onChange={(event, data) => {
          setSearch(data.value);
        }}
      />
      <Table celled className="hits">
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>Title</Table.HeaderCell>
            <Table.HeaderCell>Count</Table.HeaderCell>
          </Table.Row>
        </Table.Header>

        <Table.Body>
          {grouped.map((record) => {
            return (
              <Table.Row
                key={record.blogitem.oid}
                warning={differentIds.includes(record.blogitem.id)}
              >
                <Table.Cell>
                  <Link to={`/plog/${record.blogitem.oid}`}>
                    {record.blogitem.title}
                  </Link>{' '}
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
