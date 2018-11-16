import React from 'react';
import { Link } from 'react-router-dom';
import { toDate, isBefore, formatDistance } from 'date-fns/esm';
import { Breadcrumb, Message } from 'semantic-ui-react';

import { BASE_URL } from './Config';

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

export function BlogitemBreadcrumb({ blogitem, oid, page }) {
  if (blogitem && !oid) {
    oid = blogitem.oid;
  }
  return (
    <Breadcrumb>
      <Breadcrumb.Section link>Blogitems</Breadcrumb.Section>
      <Breadcrumb.Divider />
      <Breadcrumb.Section active={page === 'edit'}>
        {page === 'edit' ? 'Edit' : <Link to={`/plog/${oid}`}>Edit</Link>}
      </Breadcrumb.Section>
      <Breadcrumb.Divider />
      <Breadcrumb.Section active={page === 'open_graph_image'}>
        {page === 'open_graph_image' ? (
          'Open Graph Image'
        ) : (
          <Link to={`/plog/${oid}/open-graph-image`}>
            Open Graph Image{' '}
            {blogitem && `(${blogitem.open_graph_image ? 'picked!' : 'none'})`}
          </Link>
        )}
      </Breadcrumb.Section>
      <Breadcrumb.Divider />
      <Breadcrumb.Section active={page === 'images'}>
        {page === 'images' ? (
          'Images'
        ) : (
          <Link to={`/plog/${oid}/images`}>Images</Link>
        )}
      </Breadcrumb.Section>
      <Breadcrumb.Divider />
      <Breadcrumb.Section>
        <a href={BASE_URL + `/plog/${oid}`}>View</a>
      </Breadcrumb.Section>
    </Breadcrumb>
  );
}
