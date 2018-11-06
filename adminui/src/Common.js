import React from 'react';
import { toDate, isBefore, formatDistance } from 'date-fns/esm';
import { Message } from 'semantic-ui-react';

export const DisplayDate = ({ date }) => {
  if (date === null) {
    throw new Error('date is null');
  }
  const dateObj = toDate(date);
  const now = new Date();
  if (isBefore(dateObj, now)) {
    return <span title={date}>{formatDistance(date, now)} ago</span>;
  } else {
    return <span title={date}>in {formatDistance(date, now)}</span>;
  }
};

export function ShowServerError({ error }) {
  if (!error) {
    return null;
  }
  let errorMessage = (
    <p>
      <code>{error.toString()}</code>
    </p>
  );
  if (error instanceof window.Response) {
    // Let's get fancy
    errorMessage = (
      <p>
        <b>{error.status}</b> on <b>{error.url}</b>
        <br />
        <small>{error.statusText}</small>
      </p>
    );
  }
  return (
    <Message negative>
      <Message.Header>Server Error</Message.Header>
      {errorMessage}
    </Message>
  );
}
