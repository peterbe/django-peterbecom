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
      <Breadcrumb.Section>
        <Link to="/plog">Blogitems</Link>
      </Breadcrumb.Section>
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

export const formatFileSize = (bytes, decimals = 0) => {
  if (!bytes) return '0 bytes';
  var k = 1024;
  var dm = decimals + 1 || 3;
  var sizes = ['bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
  var i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

export function filterToQueryString(filterObj, overrides) {
  const copy = Object.assign(overrides || {}, filterObj);
  const searchParams = new URLSearchParams();
  Object.entries(copy).forEach(([key, value]) => {
    if (Array.isArray(value) && value.length) {
      value.forEach(v => searchParams.append(key, v));
    } else if (value) {
      searchParams.set(key, value);
    }
  });
  searchParams.sort();
  return searchParams.toString();
}
