#!/usr/bin/env node

'use strict';

const fs = require('fs');
const minimist = require('minimist');
const process = require('process');
// const search = require('./search').search;

const aws = require('aws-lib');
const env = require('node-env-file');

env(__dirname + '/.env');

if (!process.env.AWS_ACCESS_KEY_ID) {
  throw new Error('AWS_ACCESS_KEY_ID environment variable missing');
}
if (!process.env.AWS_SECRET_ACCESS_KEY) {
  throw new Error('AWS_SECRET_ACCESS_KEY environment variable missing');
}
if (!process.env.AWS_ASSOCIATE_TAG) {
  throw new Error('AWS_ASSOCIATE_TAG environment variable missing');
}
const prodAdv = aws.createProdAdvClient(
  process.env.AWS_ACCESS_KEY_ID,
  process.env.AWS_SECRET_ACCESS_KEY,
  process.env.AWS_ASSOCIATE_TAG
);

const search = (client, params, callback) => {
  const callParams = {
    ResponseGroup: 'ItemAttributes,Images,SalesRank' // need SalesRank??
  };
  let op = 'ItemSearch';
  console.log('PARAMS:', params);
  if (params.keywords) {
    callParams.Keywords = params.keywords;
    // callParams.SearchIndex = params.searchindex || 'Books'
    callParams.SearchIndex = params.searchindex || 'All';
  } else if (params.itemid) {
    callParams.ItemId = params.itemid;
    op = 'ItemLookup';
  } else {
    throw new Error('Neither keywords or itemid');
  }
  // XXX turn this into a promise instead
  return client.call(op, callParams, callback);
};

const args = process.argv.slice(2);

const argv = minimist(args, {
  boolean: ['help'],
  string: ['out', 'keyword', 'searchindex'],
  unknown: param => {
    if (param.startsWith('-')) {
      console.warn('Ignored unknown option: ' + param + '\n');
      return false;
    }
  }
});

if (argv['help']) {
  console.log('Usage: cli.js "keywords"\n\n' + '');
  process.exit(0);
}

const keyword = argv['keyword'] || argv['_'].join(' ');

const params = { keywords: keyword };
if (argv['searchindex']) {
  params.searchindex = argv['searchindex'];
}
search(prodAdv, params, (err, result) => {
  if (err) {
    console.error(err);
    process.exit(1);
  } else {
    const out = JSON.stringify(result);
    if (argv['out']) {
      try {
        fs.writeFileSync(argv['out'], out + '\n', 'utf8');
      } catch (ex) {
        console.error(ex.toString());
        process.exit(2);
      }
    } else {
      console.log(out);
    }
    process.exit(0);
  }
});
