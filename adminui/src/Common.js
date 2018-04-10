import React from 'react';

import {
  toDate,
  isBefore,
  formatDistance,
  // formatDistanceStrict,
  // differenceInSeconds,
  // differenceInMilliseconds,
} from 'date-fns/esm';

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
