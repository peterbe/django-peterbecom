import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  Button,
  Container,
  Input,
  Label,
  Loader,
  Table,
} from 'semantic-ui-react';
import useSWR from 'swr';

import { DisplayDate, ShowServerError } from './Common';

export default function Blogitems() {
  const [search, setSearch] = useState('');
  const [orderBy, setOrderBy] = useState(null);

  const apiURL = useMemo(() => {
    const base = '/api/v0/plog/';
    const sp = new URLSearchParams();
    if (search.trim()) {
      sp.set('search', search.trim());
    }
    if (orderBy) {
      sp.set('order', orderBy);
    }
    return `${base}?${sp.toString()}`;
  }, [search, orderBy]);

  const { data, error: serverError } = useSWR(apiURL, async (url) => {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`${response.status} on ${url}`);
    }
    return await response.json();
  });

  const loading = !data && !serverError;

  const orderDirection =
    orderBy && orderBy.charAt(0) === '-' ? 'descending' : 'ascending';
  const orderLabel = orderBy === 'pub_date' ? 'Published' : 'Modified';

  return (
    <Container>
      <ShowServerError error={serverError} />
      {loading && (
        <Loader
          active
          content="Loading Blogitems..."
          inline="centered"
          size="massive"
          style={{ margin: '200px 0' }}
        />
      )}
      {data && (
        <BlogitemsTable
          blogitems={data.blogitems}
          changeOrderColumn={() => {
            setOrderBy((prevState) =>
              prevState === 'pub_date' ? 'modify_date' : 'pub_date'
            );
          }}
          defaultSearch={search}
          count={data.count}
          orderDirection={orderDirection}
          orderLabel={orderLabel}
          updateFilterSearch={(search) => {
            setSearch(search);
          }}
        />
      )}
    </Container>
  );
}

function BlogitemsTable({
  blogitems,
  count,
  orderDirection,
  changeOrderColumn,
  orderLabel,
  updateFilterSearch,
  search,
}) {
  return (
    <Table celled>
      <Table.Header>
        <Table.Row>
          <Table.HeaderCell>Title ({count.toLocaleString()})</Table.HeaderCell>
          <Table.HeaderCell
            onClick={() => {
              changeOrderColumn();
            }}
            sorted={orderDirection}
          >
            {orderLabel}
          </Table.HeaderCell>
        </Table.Row>
        <Table.Row>
          <Table.HeaderCell colSpan={2}>
            <Input
              icon="search"
              list="search-autofills"
              onChange={(event) => {
                updateFilterSearch(event.target.value);
              }}
              placeholder="Search..."
              style={{ width: '90%' }}
              value={search}
            />
            {search ? (
              <Button
                icon="remove"
                onClick={() => {
                  // setSearch('');
                  updateFilterSearch('');
                  // updateFilterSearch('');
                }}
              />
            ) : null}
          </Table.HeaderCell>
        </Table.Row>
      </Table.Header>

      <Table.Body>
        {blogitems.map((item) => {
          return (
            <Table.Row key={item.oid}>
              <Table.Cell>
                <Link to={`/plog/${item.oid}`}>{item.title}</Link>
                {item.categories.map((category) => (
                  <Label
                    key={category.id}
                    onClick={() => {
                      console.warn('Not implemented');
                      // this.updateFilterCategories(category.name);
                    }}
                    size="tiny"
                    style={{ cursor: 'pointer' }}
                  >
                    {category.name}
                  </Label>
                ))}

                {item.archived && (
                  <Label color="red" size="tiny" title={item.archived}>
                    Archived
                  </Label>
                )}

                {!item._is_published ? (
                  <Label color="orange" size="tiny">
                    Published <DisplayDate date={item.pub_date} />
                  </Label>
                ) : null}

                {!item.summary && (
                  <Label circular color="brown" empty title="No summary!" />
                )}
              </Table.Cell>
              <Table.Cell>
                <DisplayDate date={item.modify_date} />
              </Table.Cell>
            </Table.Row>
          );
        })}
      </Table.Body>
    </Table>
  );
}
