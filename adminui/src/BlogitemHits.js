import { useState } from 'react';
import { Button, Header, Container, Loader, Table } from 'semantic-ui-react';
import useSWR from 'swr';

import { ShowServerError } from './Common';
import { BASE_URL } from './Config';
import { fetcher } from './fetcher';

function BlogitemHits() {
  const [loadAll, setLoadAll] = useState(false);

  let url = '/api/v0/plog/hits/';
  if (loadAll) {
    url += url.includes('?') ? '&' : '?';
    url += `limit=10000`;
  }
  const { data, error, isLoading } = useSWR(url, fetcher);

  return (
    <Container textAlign="center">
      <Header as="h1">Blogitem Hits</Header>
      <ShowServerError error={error} />
      {isLoading && (
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

      {data && <Hits hits={data.all_hits} categories={data.categories} />}
      {data && !loadAll && !isLoading && (
        <Button
          onClick={() => {
            setLoadAll(true);
          }}
        >
          Load all
        </Button>
      )}
      {data && data.summed_category_scores && (
        <Categories summedCategoryScores={data.summed_category_scores} />
      )}
    </Container>
  );
}

export default BlogitemHits;

function Hits({ categories, hits }) {
  return (
    <Table celled className="hits">
      <Table.Header>
        <Table.Row>
          <Table.HeaderCell>Title</Table.HeaderCell>
          <Table.HeaderCell>
            <abbr title="Document popularity">Pop</abbr>
          </Table.HeaderCell>
          <Table.HeaderCell>Score</Table.HeaderCell>
          <Table.HeaderCell>
            Log<sub>10</sub>(Score)
          </Table.HeaderCell>
          <Table.HeaderCell>Hits</Table.HeaderCell>
          <Table.HeaderCell>Age (days)</Table.HeaderCell>
        </Table.Row>
      </Table.Header>

      <Table.Body>
        {hits.map((record) => {
          const theseCategories = categories[record.id] || [];
          return (
            <Table.Row key={record.id}>
              <Table.Cell>
                <a
                  href={BASE_URL + record._absolute_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {record.title}
                </a>{' '}
                {theseCategories.map((name) => {
                  return (
                    <a
                      key={name}
                      className="category"
                      href={BASE_URL + `/oc-${name.replace(/ /g, '+')}`}
                    >
                      {name}
                    </a>
                  );
                })}
              </Table.Cell>
              <Table.Cell>{record.popularity.toFixed(4)}</Table.Cell>
              <Table.Cell>{record.score.toFixed(1)}</Table.Cell>
              <Table.Cell>{record.log10_score.toFixed(4)}</Table.Cell>
              <Table.Cell>{record.hits}</Table.Cell>
              <Table.Cell>{record.age}</Table.Cell>
            </Table.Row>
          );
        })}
      </Table.Body>
    </Table>
  );
}

function Categories({ summedCategoryScores }) {
  return (
    <div style={{ marginTop: 50 }}>
      <Header as="h2">Categories</Header>
      <Table celled>
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>Name</Table.HeaderCell>
            <Table.HeaderCell>Count</Table.HeaderCell>
            <Table.HeaderCell>Sum</Table.HeaderCell>
            <Table.HeaderCell>Average</Table.HeaderCell>
            <Table.HeaderCell>Median</Table.HeaderCell>
          </Table.Row>
        </Table.Header>

        <Table.Body>
          {summedCategoryScores.map((each) => {
            return (
              <Table.Row key={each.name}>
                <Table.Cell>
                  <a
                    href={BASE_URL + `/oc-${each.name.replace(/ /g, '+')}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={`Filter by the '${each.name}' category`}
                  >
                    {each.name}
                  </a>{' '}
                  (
                  <a href={`/plog?search=cat:${encodeURIComponent(each.name)}`}>
                    list
                  </a>
                  )
                </Table.Cell>
                <Table.Cell>{each.count}</Table.Cell>
                <Table.Cell>{each.sum.toFixed(2)}</Table.Cell>
                <Table.Cell>{each.avg.toFixed(2)}</Table.Cell>
                <Table.Cell>{each.med.toFixed(2)}</Table.Cell>
              </Table.Row>
            );
          })}
        </Table.Body>
      </Table>
    </div>
  );
}
