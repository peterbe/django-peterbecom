import React, { useState, useMemo } from 'react';
import { Link, createSearchParams, useSearchParams } from 'react-router-dom';
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
import { fetcher } from './fetcher';

export default function Blogitems() {
  const [searchParams, setSearchParams] = useSearchParams();

  const apiURL = useMemo(() => {
    const base = '/api/v0/plog/';
    const sp = new URLSearchParams();

    if (searchParams.get('search')) {
      sp.set('search', searchParams.get('search'));
    }
    if (searchParams.get('orderBy')) {
      sp.set('order', searchParams.get('orderBy'));
    }
    return `${base}?${sp.toString()}`;
  }, [searchParams]);

  const { data, error: serverError } = useSWR(apiURL, fetcher);

  const loading = !data && !serverError;
  const orderBy = searchParams.get('orderBy');
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
            setSearchParams(
              createSearchParams({
                ...Object.fromEntries(searchParams),
                orderBy:
                  searchParams.get('orderBy') === 'pub_date'
                    ? 'modify_date'
                    : 'pub_date',
              }).toString()
            );
          }}
          search={searchParams.get('search') || ''}
          count={data.count}
          orderDirection={orderDirection}
          orderLabel={orderLabel}
          updateFilterSearch={(search) => {
            const sp = createSearchParams({
              ...Object.fromEntries(searchParams),
            });
            if (search) {
              sp.set('search', search);
            } else if (sp.get('search')) {
              sp.delete('search');
            }
            setSearchParams(sp);
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
  const [ownSearch, setOwnSearch] = useState(search);
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        updateFilterSearch(ownSearch);
      }}
    >
      <Table celled>
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>
              Title ({count.toLocaleString()})
            </Table.HeaderCell>
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
                  setOwnSearch(event.target.value);
                }}
                placeholder="Search..."
                style={{ width: '90%' }}
                value={ownSearch}
              />
              {search ? (
                <Button
                  type="button"
                  icon="remove"
                  onClick={() => {
                    setOwnSearch('');
                    updateFilterSearch('');
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
    </form>
  );
}
