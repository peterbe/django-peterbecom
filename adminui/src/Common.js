import React from 'react';
import { Link } from 'react-router-dom';
import { parseISO, isBefore, formatDistance } from 'date-fns/esm';
import { Breadcrumb, Message } from 'semantic-ui-react';

import { BASE_URL } from './Config';

export function DisplayDate({ date, now, prefix }) {
  prefix = prefix || 'in';
  if (date === null) {
    throw new Error('date is null');
  }
  const dateObj = typeof date === 'string' ? parseISO(date) : date;
  const nowObj = now ? parseISO(now) : new Date();
  if (isBefore(dateObj, nowObj)) {
    return <span title={dateObj}>{formatDistance(dateObj, nowObj)} ago</span>;
  } else {
    return (
      <span title={dateObj}>
        {prefix} {formatDistance(dateObj, nowObj)}
      </span>
    );
  }
}

export function ShowServerError({ error }) {
  if (!error) {
    return null;
  }
  let err;
  if (error instanceof window.Response) {
    err = (
      <p>
        <b>{error.status}</b> on <b>{error.url}</b>
        <br />
        <small>{error.statusText}</small>
      </p>
    );
  } else if (error instanceof Error) {
    err = (
      <p>
        <code>{error.toString()}</code>
      </p>
    );
  } else {
    err = (
      <pre style={{ textAlign: 'left' }}>
        {JSON.stringify(error.errors ? error.errors : error, null, 3)}
      </pre>
    );
  }
  return (
    <Message negative>
      <Message.Header>Server Error</Message.Header>
      {err}
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
      <Breadcrumb.Section active={page === 'awspa'}>
        {page === 'awspa' ? (
          'AWSPA'
        ) : (
          <Link to={`/plog/${oid}/awspa`}>
            AWSPA {blogitem && `(${blogitem.awsproducts_count})`}
          </Link>
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

export function equalArrays(array1, array2) {
  return (
    array1.length === array2.length &&
    array1.every((value, index) => value === array2[index])
  );
}
