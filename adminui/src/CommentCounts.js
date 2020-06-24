import React from 'react';
import { Select, Container, Header, Table } from 'semantic-ui-react';
import useSWR from 'swr';
import { Bar } from 'react-roughviz';
import { ShowServerError, useLocalStorage } from './Common';

export default function CommentCounts({ accessToken }) {
  const [intervalDays, setIntervalDays] = useLocalStorage(
    'comment-counts-interval-days',
    28
  );

  const { data, error } = useSWR(
    `/api/v0/plog/comments/counts/?days=${intervalDays}`,
    async (url) => {
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      if (!response.ok) {
        throw new Error(`${response.status} on ${url}`);
      }
      return await response.json();
    },
    {
      revalidateOnFocus: process.env.NODE_ENV === 'development',
    }
  );

  return (
    <Container textAlign="center">
      <Header as="h1">Comment Counts</Header>
      <ShowServerError error={error} />
      {!data && !error && <p>Loading...</p>}
      {data && !error && <ShowDays dates={data.dates} />}
      {data && (
        <Select
          placeholder="Interval"
          value={intervalDays}
          options={intervalDaysOptions}
          onChange={(event, data) => {
            setIntervalDays(data.value);
          }}
        />
      )}
    </Container>
  );
}

const intervalDaysOptions = [
  { key: 7, value: 7, text: '1 week (7 days)' },
  { key: 28, value: 28, text: '1 month (28 days)' },
  { key: 90, value: 90, text: '3 month (90 days)' },
  { key: 365, value: 365, text: '1 year (365 days)' },
];

function ShowDays({ dates }) {
  const data = {
    labels: dates.map((date) => date.date),
    values: dates.map((date) => date.count),
  };
  return (
    <div>
      <Bar
        data={data}
        labels="flavor"
        values="price"
        width={1100}
        height={300}
      />
      <Table celled>
        <Table.Header>
          <Table.Row>
            <Table.HeaderCell>Date</Table.HeaderCell>
            <Table.HeaderCell>Count</Table.HeaderCell>
          </Table.Row>
        </Table.Header>

        <Table.Body>
          {dates.map((day) => {
            return (
              <Table.Row key={day.date}>
                <Table.Cell>{day.date}</Table.Cell>
                <Table.Cell>{day.count}</Table.Cell>
              </Table.Row>
            );
          })}
        </Table.Body>
      </Table>
    </div>
  );
}
