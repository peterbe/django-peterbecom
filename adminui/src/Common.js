import React from 'react';
import { Link } from 'react-router-dom';
import { toDate, isBefore, formatDistance } from 'date-fns/esm';

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

export const Breadcrumbs = ({ active, tos = [] }) => {
  return (
    <div className="ui breadcrumb">
      <Link to="/" className="section">
        Home
      </Link>
      <span className="divider">/</span>
      {tos.map(each => {
        return [
          <Link key={each.to} to={each.to}>
            {each.name}
          </Link>,
          <span key={each.to + 'divider'} className="divider">
            /
          </span>
        ];
      })}
      <div className="active section">{active}</div>
    </div>
  );
};
